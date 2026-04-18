## xnch + Nexi Local Infrastructure Design

### 1. Process Architecture

Two nodes. Clear separation. Primary does all heavy work. Secondary is overflow and lightweight model serving only.

---

**Primary Node (i9 + RTX 3090)**

```
Process             Port    GPU?    Role
─────────────────────────────────────────────────────
xnch-server         8100    No      Control plane API (FastAPI)
nexi-engine         8200    No      Decision engine (FastAPI)
vllm-primary        8300    Yes     Main LLM inference (3090, ~18GB)
memory-store        8400    No      SQLite + pattern store (FastAPI wrapper)
execution-runner    8500    No      Action executor (subprocess manager)
audit-logger        8600    No      Append-only audit sink (lightweight)
```

All processes run as plain Python services. No containers required for v0. Each is a systemd user service or a tmux session on day 1.

**Secondary Node (i7 + GTX 1650)**

```
Process             Port    GPU?    Role
─────────────────────────────────────────────────────
vllm-secondary      8300    Yes     Small model inference (1650, ~3.5GB)
nexi-worker         8201    No      Overflow reasoning worker (CPU)
```

Secondary is optional on day 1. Primary is fully self-sufficient. Secondary adds capacity for parallel requests and fallback model serving.

---

### 2. Component Placement

**xnch modules — Primary Node, port 8100**

```
xnch-server/
  ├── session.py          # session init, actor resolution
  ├── policy_engine.py    # rule evaluation against active policy set
  ├── governance.py       # RBAC, role resolution from local store
  ├── verdict.py          # /verdict endpoint, token signing
  ├── execution_gate.py   # token validation, execution authorization
  └── audit.py            # sync audit write before verdict response
```

All CPU. No GPU. SQLite for governance store and policy store. Policies are YAML files loaded at startup, hot-reloadable via `SIGHUP`. JWT signing with a local RS256 keypair generated on first run.

**Nexi modules — Primary Node, port 8200**

```
nexi-engine/
  ├── intent.py           # intent interpretation, ambiguity scoring
  ├── context.py          # calls xnch /memory/read, pins manifest
  ├── generator.py        # calls vllm-primary (or secondary) via HTTP
  ├── policy_filter.py    # parallel /policy/check calls to xnch
  ├── evaluator.py        # scoring, weight application
  ├── simulator.py        # outcome simulation (conditional)
  ├── selector.py         # decision record assembly
  └── session.py          # session state management (in-memory, per request)
```

All CPU. Nexi itself never touches GPU. Nexi's GPU usage is indirect — through calls to vllm-primary.

**Memory System — Primary Node, port 8400**

```
memory-store/
  ├── episodic.py         # TimescaleDB-lite: SQLite with time-indexed episodes
  ├── semantic.py         # Pattern store: SQLite with JSONB-equivalent (JSON1 extension)
  ├── policy_store.py     # Policy file loader + version tracker
  └── api.py              # REST wrapper: /memory/read, /memory/write, /pattern/update
```

Single SQLite file per store type. Three files total:
```
~/.xnch/data/episodic.db
~/.xnch/data/semantic.db
~/.xnch/data/policy.db
```

SQLite with WAL mode. Single writer, multiple readers. Sufficient for single-user, local-first system. No PostgreSQL, no TimescaleDB overhead on day 1.

**Model Runtimes**

```
Primary (3090, 24GB VRAM):
  vllm serve --model mistralai/Mistral-7B-Instruct-v0.3 \
             --port 8300 \
             --gpu-memory-utilization 0.75 \
             --max-model-len 8192

  # 0.75 = ~18GB VRAM. Leaves 6GB headroom for OS + other GPU processes.
  # Mistral 7B at 4-bit quant fits in ~4GB, at fp16 fits in ~14GB.
  # Run fp16 on 3090 for quality. Reserve quant for 1650.

Secondary (1650, 4GB VRAM):
  vllm serve --model TheBloke/Mistral-7B-Instruct-v0.1-GPTQ \
             --port 8300 \
             --gpu-memory-utilization 0.85 \
             --quantization gptq \
             --max-model-len 4096

  # GPTQ 4-bit fits in ~4GB. Tight but viable.
  # Fallback only — not primary inference path.
```

**Execution Runner — Primary Node, port 8500**

```
execution-runner/
  ├── runner.py           # receives action_spec + validates execution_token
  ├── handlers/
  │   ├── shell.py        # shell command execution (subprocess)
  │   ├── file.py         # file system operations
  │   ├── http.py         # outbound HTTP actions
  │   └── model.py        # model management actions (load/unload/deploy)
  └── outcome.py          # posts outcome back to xnch /execution/outcome
```

Execution runner validates the JWT token independently using xnch's public key (stored locally at `~/.xnch/keys/public.pem`). Does not trust Nexi's assertion that xnch approved the action.

---

### 3. Inter-Process Communication

Flat and simple. All HTTP over localhost. No message queue on day 1. No gRPC. No shared memory.

```
CLI
  │  HTTP POST localhost:8200/session/start
  ▼
nexi-engine (8200)
  │  HTTP POST localhost:8100/session/init       [xnch: actor resolution]
  │  HTTP POST localhost:8100/memory/read        [xnch → memory-store: context]
  │  HTTP POST localhost:8300/v1/completions     [vllm-primary: generation]
  │  HTTP GET  localhost:8100/policy/check ×N   [xnch: parallel dry-run]
  │  HTTP POST localhost:8100/verdict            [xnch: final authorization]
  │  HTTP POST localhost:8500/execute            [execution-runner: dispatch]
  ▼
execution-runner (8500)
  │  HTTP POST localhost:8100/execution/outcome  [xnch: outcome report]
  ▼
xnch (8100)
  │  HTTP POST localhost:8200/callback/outcome   [nexi: memory write trigger]
  │  HTTP POST localhost:8400/memory/write       [memory-store: episode complete]
```

All calls are localhost. Latency is sub-millisecond for everything except the vllm call. No service discovery needed. Ports are hardcoded in a single config file:

```yaml
# ~/.xnch/config.yaml
services:
  xnch: "http://localhost:8100"
  nexi: "http://localhost:8200"
  memory: "http://localhost:8400"
  model_primary: "http://localhost:8300"
  model_secondary: "http://192.168.x.x:8300"  # secondary node IP
  execution: "http://localhost:8500"
  audit: "http://localhost:8600"
```

Secondary node communication is LAN HTTP. Same interface, different IP. Nexi's generator.py checks primary first, falls back to secondary if primary returns 503 or times out after 5s.

**Audit logger** receives fire-and-forget UDP datagrams from xnch on port 8600. Chosen because audit must never block the verdict path. UDP packet loss is acceptable — audit logger also receives a sync write at verdict time for critical records. UDP is for high-frequency trace events.

---

### 4. Model Execution Strategy

**RTX 3090 — Primary inference**

```
Model: Mistral-7B-Instruct-v0.3 (fp16)
VRAM:  ~14GB loaded, 18GB ceiling (0.75 utilization cap)
Role:  Option generation (Step 5), all primary Nexi calls
Context window: 8192 tokens
Concurrency: 1 request at a time (single user, no queue needed)
```

Why Mistral 7B fp16 over a larger quantized model: at single-user, single-request concurrency, quality matters more than throughput. fp16 gives better reasoning quality for option generation than a 13B at 4-bit on the same VRAM budget.

**GTX 1650 — Fallback and lightweight tasks**

```
Model: Mistral-7B-Instruct-v0.1-GPTQ (4-bit)
VRAM:  ~3.5GB loaded, 3.8GB ceiling (0.85 cap — tight)
Role:  Fallback when 3090 unavailable, low-complexity intent classification
Context window: 4096 tokens (reduced due to VRAM constraint)
Concurrency: 1 request, longer queue tolerance
```

**CPU inference — last resort**

```
Runtime: llama.cpp (via llama-cpp-python)
Model:   Mistral-7B-Instruct-v0.3.Q4_K_M.gguf
RAM:     ~5GB system RAM
Speed:   ~8–15 tokens/sec on i9 (viable, slow)
Trigger: both GPU nodes unavailable
```

llama.cpp binary kept at `~/.xnch/models/llama.cpp/`. Invoked directly by generator.py as a subprocess fallback. Not a running service — started on demand, killed after response.

**Model selection logic in generator.py:**

```python
async def call_model(prompt: str, context_tokens: int) -> list[Option]:
    if context_tokens > 6000:
        target = config.model_primary   # only 3090 has 8192 context
    else:
        target = config.model_primary   # prefer primary always

    try:
        response = await http_post(target, prompt, timeout=30)
        return parse_options(response)
    except (TimeoutError, ConnectionError):
        try:
            response = await http_post(config.model_secondary, prompt, timeout=45)
            return parse_options(response)
        except (TimeoutError, ConnectionError):
            return cpu_inference_fallback(prompt)  # llama.cpp subprocess
```

---

### 5. Execution Flow Mapping Across Processes

```
TIME    PROCESS         ACTION
──────────────────────────────────────────────────────────────────
0ms     CLI             POST /session/start → nexi:8200
5ms     nexi:8200       POST /session/init → xnch:8100
25ms    xnch:8100       resolve actor, pin versions → return session_ctx
30ms    nexi:8200       interpret intent, compute ambiguity
35ms    nexi:8200       POST /memory/read → xnch:8100
40ms    xnch:8100       query memory-store:8400 (3 parallel SQLite reads)
120ms   xnch:8100       return context manifest → nexi:8200
125ms   nexi:8200       construct generation prompt
130ms   nexi:8200       POST /v1/completions → vllm:8300
        [vllm inference: 800–3000ms depending on prompt length]
3130ms  vllm:8300       return 5 structured options → nexi:8200
3135ms  nexi:8200       validate option schema
3140ms  nexi:8200       POST /policy/check ×5 → xnch:8100 (parallel)
3200ms  xnch:8100       evaluate all 5 options against policy set
3220ms  xnch:8100       return 5 verdicts → nexi:8200
3225ms  nexi:8200       drop blocked options, update modified options
3230ms  nexi:8200       score surviving options (in-memory)
3245ms  nexi:8200       simulate top 2 if risk threshold exceeded
3290ms  nexi:8200       select winner, assemble decision record
3295ms  nexi:8200       POST /verdict → xnch:8100
3310ms  xnch:8100       verify state version, re-evaluate, emit audit record
3330ms  xnch:8100       sign execution token (RS256, local key)
3340ms  xnch:8100       return verdict + token → nexi:8200
3345ms  nexi:8200       POST /execute → execution-runner:8500
3350ms  execution:8500  validate token against public key
3355ms  execution:8500  return ACCEPTED + execution_ref → nexi:8200
3360ms  nexi:8200       return EXECUTING response → CLI
        [execution runs async]
3360ms  CLI             displays: "Decision made. Executing. ref: exec_cc20"
        [execution completes: 5000–60000ms later]
41360ms execution:8500  POST /execution/outcome → xnch:8100
41370ms xnch:8100       write episode completion to memory-store:8400
41380ms xnch:8100       POST /callback/outcome → nexi:8200
41390ms nexi:8200       POST /memory/write → xnch:8100 (decision outcome record)
41400ms xnch:8100       write to memory-store:8400
41410ms xnch:8100       POST outcome → nexi:8200 confirmed
41415ms nexi:8200       check prediction delta, flag pattern if needed
41420ms xnch:8100       push final status → CLI (polling or SSE)
```

CLI polls `GET /session/{session_id}/status` on nexi:8200 every 2 seconds while `status=EXECUTING`. nexi:8200 returns cached status updated by the xnch callback.

---

### 6. Resource Management

**VRAM allocation — 3090**

```
Reserved for OS/display:     ~1GB
vllm-primary ceiling:        18GB  (--gpu-memory-utilization 0.75)
Headroom buffer:              5GB
Total:                       24GB
```

vllm manages its own KV cache within the 18GB ceiling. No external VRAM management needed. The `--gpu-memory-utilization 0.75` flag is the single control lever.

One active inference request at a time. Single-user system — no queue needed. If a second request arrives while one is processing (shouldn't happen in CLI-first single-user), nexi returns 429 with retry-after estimate based on `avg_execution_ms` from pattern store.

**VRAM protection — prevent overflow**

```python
# In generator.py, before calling vllm
MAX_INPUT_TOKENS = 6000  # conservative limit, leaves room for KV cache growth

if estimated_tokens(prompt) > MAX_INPUT_TOKENS:
    # truncate context summary, not the intent or schema
    prompt = truncate_context_section(prompt, MAX_INPUT_TOKENS)
```

vllm's `--max-model-len 8192` is the hard ceiling. Requests that exceed it are rejected by vllm with a clear error — generator.py catches this and retries with a truncated prompt before escalating to secondary.

**CPU concurrency**

xnch, nexi, memory-store, execution-runner are all FastAPI with `uvicorn --workers 1`. Single-user system — one worker each is correct. No thread pool overhead, no worker management complexity. If a request takes 5s, the next one waits. Acceptable for CLI-first single-user.

**SQLite WAL mode** — enabled on all three databases at startup:

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")  # faster than FULL, safe with WAL
conn.execute("PRAGMA cache_size=-64000")   # 64MB page cache
```

This allows concurrent reads while a write is in progress. Critical for the memory-store since xnch reads and writes simultaneously during execution + callback flow.

---

### 7. Failure and Fallback

**vllm-primary (3090) down**

```
generator.py detects: ConnectionError or timeout > 30s
Action: retry once (in case of transient startup delay)
Then: switch to model_secondary (1650 over LAN)
If secondary also down: cpu_inference_fallback() via llama.cpp subprocess
If llama.cpp fails: return DEGRADED to nexi, use rule-based option generator
Rule-based generator: pulls 3 conservative options directly from policy memory
Decision record flagged: generation_path=RULE_BASED
```

**xnch down**

```
nexi cannot proceed. Hard dependency.
Returns 503 to CLI immediately.
No partial execution — no xnch means no policy enforcement, no execution tokens.
CLI displays: "Control plane unavailable. Start xnch-server and retry."
Recovery: xnch restarts in <5s (no state in memory — all state is in SQLite files)
```

**memory-store down**

```
xnch cannot load context manifest (Step 4 fails).
nexi returns DEGRADED — does not proceed with empty context.
xnch cannot write audit records — halts verdict issuance.
Recovery: memory-store restarts in <3s (SQLite files persist on disk)
No data loss: SQLite WAL ensures committed transactions survive crash.
```

**execution-runner down**

```
Token issued but execution-runner unreachable.
nexi returns EXECUTING to CLI, execution_ref issued.
Execution never starts — outcome never reported.
After 5min: xnch background job scans for PENDING episodes older than TTL.
Flags them as STALE, notifies CLI on next poll.
CLI displays: "Execution stale. Runner may be down. Check execution-runner:8500."
Re-execution: user resubmits. Idempotency key prevents duplicate episode creation.
```

**Secondary node (1650) unreachable**

```
This is a fallback node — its failure has no impact on primary path.
generator.py skips it, goes directly to cpu_inference_fallback.
No alert needed. Log the miss, continue.
```

**SQLite corruption**

```
Detected at startup via PRAGMA integrity_check.
If episodic.db corrupt: system starts in degraded mode (no outcome history).
  Nexi proceeds but outcome_score defaults to 0.5 for all options.
If semantic.db corrupt: pattern store rebuilds from episodic history on next batch run.
  Background job: python -m memory.rebuild_semantic --from-episodic
If policy.db corrupt: xnch refuses to start. Policies are the hard constraint source.
  Recovery: restore from ~/.xnch/backups/policy.db.bak (daily backup, cron job)
```

---

### 8. Minimal Deployment Plan

**Directory structure**

```
~/.xnch/
  config.yaml
  keys/
    private.pem       # generated on first run
    public.pem
  data/
    episodic.db
    semantic.db
    policy.db
  policies/           # YAML policy files, loaded by xnch at startup
    ml_deploy.yaml
    infra.yaml
    defaults.yaml
  models/
    llama.cpp/        # llama.cpp binary + GGUF model for CPU fallback
  logs/
    xnch.log
    nexi.log
    memory.log
    execution.log
  backups/            # daily cron backup of .db files

~/xnch-system/        # source code
  xnch/
  nexi/
  memory/
  execution/
  cli/
  shared/             # config loader, token utils, schema definitions
```

**Installation (Primary Node, day 1)**

```bash
# 1. Python environment
python3 -m venv ~/.xnch/venv
source ~/.xnch/venv/bin/activate
pip install fastapi uvicorn httpx vllm pyjwt pyyaml aiohttp

# 2. Generate keypair
mkdir -p ~/.xnch/keys
openssl genrsa -out ~/.xnch/keys/private.pem 2048
openssl rsa -in ~/.xnch/keys/private.pem -pubout -out ~/.xnch/keys/public.pem

# 3. Initialize databases
python -m shared.db_init   # creates episodic.db, semantic.db, policy.db with schema

# 4. Load default policies
cp ~/xnch-system/policies/defaults/* ~/.xnch/policies/

# 5. Start vllm (3090)
CUDA_VISIBLE_DEVICES=0 vllm serve mistralai/Mistral-7B-Instruct-v0.3 \
  --port 8300 \
  --gpu-memory-utilization 0.75 \
  --max-model-len 8192 \
  --dtype float16 &

# Wait for vllm to load (~60–90s for 7B fp16)
# 6. Start all services (in tmux or separate terminals)
uvicorn memory.api:app --port 8400 --workers 1 &
uvicorn xnch.main:app --port 8100 --workers 1 &
uvicorn nexi.main:app --port 8200 --workers 1 &
uvicorn execution.runner:app --port 8500 --workers 1 &
python -m audit.logger --port 8600 &   # UDP listener, lightweight

# 7. Verify
curl localhost:8100/health   # {"status":"ok","policy_version":"v1.0.0"}
curl localhost:8200/health   # {"status":"ok","model":"connected"}
curl localhost:8400/health   # {"status":"ok","episodic":"0 records"}

# 8. Run CLI
python -m cli.main "deploy model llama3-8b to inference cluster"
```

**tmux layout for day 1 (one command)**

```bash
# start_xnch.sh — run this to bring everything up
#!/bin/bash
tmux new-session -d -s xnch -n vllm
tmux send-keys -t xnch:vllm "CUDA_VISIBLE_DEVICES=0 vllm serve mistralai/Mistral-7B-Instruct-v0.3 --port 8300 --gpu-memory-utilization 0.75 --max-model-len 8192" Enter

tmux new-window -t xnch -n services
tmux send-keys -t xnch:services "source ~/.xnch/venv/bin/activate && uvicorn memory.api:app --port 8400 & uvicorn xnch.main:app --port 8100 & uvicorn nexi.main:app --port 8200 & uvicorn execution.runner:app --port 8500 & python -m audit.logger --port 8600" Enter

tmux new-window -t xnch -n cli
tmux send-keys -t xnch:cli "source ~/.xnch/venv/bin/activate && cd ~/xnch-system" Enter

tmux attach -t xnch
```

**Secondary node setup (day 2, optional)**

```bash
# On secondary node (i7 + 1650)
pip install fastapi uvicorn vllm

CUDA_VISIBLE_DEVICES=0 vllm serve TheBloke/Mistral-7B-Instruct-v0.1-GPTQ \
  --port 8300 \
  --quantization gptq \
  --gpu-memory-utilization 0.85 \
  --max-model-len 4096 &

uvicorn nexi.main:app --port 8201 --workers 1 &  # nexi-worker, CPU only

# Update primary node config.yaml:
# model_secondary: "http://192.168.x.x:8300"
```

**Daily backup cron**

```bash
# crontab -e
0 2 * * * cp ~/.xnch/data/episodic.db ~/.xnch/backups/episodic.db.$(date +\%Y\%m\%d)
0 2 * * * cp ~/.xnch/data/policy.db ~/.xnch/backups/policy.db.bak
0 2 * * * find ~/.xnch/backups -name "episodic.db.*" -mtime +7 -delete
```

**Pattern extraction cron (runs every 6 hours)**

```bash
0 */6 * * * ~/.xnch/venv/bin/python -m memory.extract_patterns >> ~/.xnch/logs/patterns.log 2>&1
```

**What you have at end of day 1:**

A fully running xnch + Nexi system. CLI takes natural language input. xnch enforces policies from YAML files. Nexi generates options via Mistral 7B on the 3090, filters through policy, scores, selects, and dispatches to the execution runner. Every decision is logged. Memory starts accumulating from the first run. The system improves from episode 1.