## xnch Ecosystem — Complete Tech Stack

### 1. Core Language & Runtime

**Python 3.11+**

No alternatives considered seriously. The entire AI/ML toolchain — vllm, transformers, llama-cpp-python, sentence-transformers — is Python-native. Fighting that with Rust or Go for the core services means writing FFI bridges on day one. Python 3.11 delivers meaningful performance improvements over 3.10 (25–60% faster on benchmark loops). asyncio is mature, uvicorn is production-grade, and the single-developer constraint means language switching cost is real.

Where Python is too slow: it won't be. The bottleneck is always the model inference call or SQLite I/O, not Python execution. Optimize the actual bottleneck, not the language.

**Runtime: CPython 3.11, managed via `pyenv`**

```bash
pyenv install 3.11.9
pyenv local 3.11.9
```

One virtualenv per service. Not a monorepo with shared env — each service has isolated dependencies. Prevents version conflicts as services evolve independently.

---

### 2. Interface Layer

**CLI: `Typer`**
**API: `FastAPI` + `Uvicorn`**

Typer for the CLI because it is built on Click, uses Python type hints directly, and generates help text automatically. Zero boilerplate for a well-typed CLI. The CLI is the primary human interface — it must be clean, not hacked together with argparse.

FastAPI for every internal service API because: automatic OpenAPI docs (useful for debugging during build), native async support, Pydantic v2 validation on every request and response boundary, and it is the de facto standard for Python microservices. No REST framework has better async + validation ergonomics in Python today.

Uvicorn as the ASGI server. Single worker per service (single-user system). `--reload` during development, production config without reload in deployment.

```python
# CLI entry point pattern
import typer
app = typer.Typer()

@app.command()
def run(
    input: str = typer.Argument(..., help="Natural language command"),
    priority: str = typer.Option("NORMAL", help="LOW|NORMAL|HIGH|CRITICAL"),
    trace: bool = typer.Option(False, help="Show full reasoning trace")
):
    ...
```

**Pydantic v2** for all data contracts between components. Every inter-service payload is a Pydantic model. This is not optional — untyped dicts at service boundaries are how systems become unmaintainable. Pydantic v2 is 5–50x faster than v1 on validation, which matters when policy dry-runs validate N options in parallel.

---

### 3. Core Engine (Nexi)

**Orchestration: Pure Python async — no framework**

Nexi's session flow is a linear async pipeline. It does not need a DAG executor, a workflow engine, or LangChain. Those add abstraction over a problem that is already solved by `async/await` and `asyncio.gather`. LangChain specifically is excluded — it abstracts the model call in ways that make the output contract non-deterministic and the debugging surface enormous.

```python
async def run_session(request: NexiRequest) -> DecisionPackage:
    intent = await interpret_intent(request)
    if intent.ambiguity_score > AMBIGUITY_THRESHOLD:
        return clarification_required(intent)
    manifest = await load_context(intent)
    options = await generate_options(intent, manifest)
    clean_options = await filter_by_policy(options, manifest)
    scored = await evaluate_options(clean_options, manifest)
    if needs_simulation(scored, intent):
        scored = await simulate_outcomes(scored, manifest)
    decision = select_best(scored)
    verdict = await submit_verdict(decision, manifest)
    return build_decision_package(decision, verdict)
```

That is the entire Nexi session. It maps directly to the pipeline defined earlier. No framework needed.

**Async HTTP client: `httpx` with `AsyncClient`**

All Nexi → xnch and Nexi → vllm calls use httpx AsyncClient. Connection pooling per service, configured at startup. Not aiohttp — httpx has better timeout handling and a cleaner API.

```python
# Shared HTTP clients, initialized once at startup
xnch_client = httpx.AsyncClient(base_url=config.xnch_url, timeout=10.0)
model_client = httpx.AsyncClient(base_url=config.model_primary_url, timeout=60.0)
```

**Parallel policy checks: `asyncio.gather`**

```python
verdicts = await asyncio.gather(*[
    xnch_client.get("/policy/check", json=opt.dict())
    for opt in options
], return_exceptions=True)
```

No threading. No process pool. asyncio.gather handles N concurrent HTTP calls to xnch without blocking. Exceptions are returned as values, not raised — each option's failure is handled independently.

---

### 4. Control Plane (xnch)

**Policy Engine: `py-rego` (OPA Python bindings) or custom DSL**

Two options, chosen based on day-one complexity tolerance:

Option A (day 1): Custom policy evaluator using Python dataclasses + simple expression evaluation. Policies are YAML files. Evaluation is a pure Python function. Fast to build, zero dependencies.

```yaml
# ~/.xnch/policies/ml_deploy.yaml
policy_id: "ml.deploy.gpu_node_only"
version: "1.0.0"
scope:
  intent_classes: [EXECUTION]
  entity_classes: [ML_MODEL]
  actor_roles: [OPERATOR, ADMIN]
rule:
  condition: "action.spec.node_type == 'cpu'"
  verdict: BLOCK
  reason: "ML model deployment requires GPU node"
enforcement_level: HARD_BLOCK
```

Option B (week 2+): Integrate `python-opa-client` against a local OPA server binary. OPA gives you Rego — a real policy language with proper boolean logic, set operations, and rule composition. The OPA binary is a single static executable, no dependencies.

**Recommendation**: Start with Option A. Wire up the YAML evaluator. Switch to OPA when policy complexity requires it (rule composition, policy-as-code testing). The interface xnch exposes to Nexi does not change — only the internal evaluator swaps.

**JWT signing: `python-jose` with RS256**

Execution tokens are RS256 JWTs signed with the local private key. `python-jose` is the most maintained Python JWT library. The execution runner holds only the public key — it never touches the private key. Standard asymmetric signing, no custom crypto.

```python
from jose import jwt

def issue_execution_token(action_hash: str, actor_id: str, ttl_ms: int) -> str:
    payload = {
        "action_hash": action_hash,
        "actor_id": actor_id,
        "exp": time.time() + (ttl_ms / 1000),
        "iss": "xnch",
        "jti": str(uuid4())
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
```

---

### 5. Memory & Storage

**Primary store: SQLite via `sqlite-utils` + raw `sqlite3`**

Three databases, one library. `sqlite-utils` for schema management and inserts. Raw `sqlite3` for complex queries where full SQL control is needed.

SQLite is the correct choice here. It is not a toy — it handles millions of rows, supports WAL concurrent reads, has a JSON1 extension for semi-structured data, and requires zero infrastructure. The alternative (PostgreSQL) adds a daemon, connection pooling, and operational overhead for zero benefit at single-user scale.

```python
import sqlite_utils

db = sqlite_utils.Database("~/.xnch/data/episodic.db")
db["episodes"].insert(episode.dict(), pk="episode_id")
db["episodes"].create_index(["intent_class", "entity_class", "created_at"])
```

WAL mode + performance pragmas set at connection init:

```python
def configure_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-65536")   # 64MB
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456") # 256MB mmap
```

**Schema approach: typed columns + JSONB-equivalent**

SQLite's JSON1 extension (`json_extract`, `json_each`) gives you JSONB-equivalent querying without a full document store. The `context_signature` and `outcome_delta` fields are stored as JSON text, queried with `json_extract`.

```sql
SELECT pattern_id, success_rate, confidence
FROM patterns
WHERE action_type = ?
  AND entity_class = ?
  AND json_extract(context_signature, '$.actor_role') = ?
  AND status = 'ACTIVE'
  AND confidence > 0.3
ORDER BY confidence DESC
LIMIT 3
```

**Semantic/vector layer: `sqlite-vec`**

`sqlite-vec` is a SQLite extension that adds vector search directly inside SQLite. No separate Chroma, no Qdrant, no Weaviate. Install as a Python package, load as a SQLite extension.

Used for: similarity matching on context signatures when exact tuple matching returns no results. If Nexi is evaluating a novel `(action_type, entity_class)` combination, `sqlite-vec` finds the nearest known pattern by embedding similarity.

```python
import sqlite_vec

db.conn.enable_load_extension(True)
sqlite_vec.load(db.conn)

# Store pattern embedding
db.execute("""
    INSERT INTO pattern_vectors(pattern_id, embedding)
    VALUES (?, vec_f32(?))
""", [pattern_id, embedding_bytes])

# Query nearest patterns
db.execute("""
    SELECT pattern_id, distance
    FROM pattern_vectors
    WHERE embedding MATCH vec_f32(?)
    ORDER BY distance LIMIT 5
""", [query_embedding_bytes])
```

Embeddings generated by `sentence-transformers` (all-MiniLM-L6-v2, 22MB, runs on CPU, 384-dim). No GPU needed for embedding generation at this scale.

**Schema migrations: `sqlite-utils` migrate pattern**

```python
# Version-controlled migrations in shared/migrations/
def migrate_v1_to_v2(db):
    db["episodes"].add_column("prediction_delta", float, not_null=False)
    db["episodes"].create_index(["entity_class", "execution_outcome"])
```

Migrations run at service startup, idempotent.

---

### 6. Model Layer

**Primary reasoning model: Mistral-7B-Instruct-v0.3 (fp16)**

Runs on RTX 3090 via vllm. Chosen for: strong instruction following, 8192 context window, fp16 quality without quantization artifacts, open weights (no API dependency), and active community support. Mistral 7B outperforms larger quantized models on structured output tasks, which is the primary use case here (option generation with schema constraints).

**Structured output enforcement: vllm guided generation**

vllm supports `guided_json` — constrain the model's output to a JSON schema at the sampling level. This is not prompt-based schema enforcement (unreliable). It is token-level logit masking against the schema. The model literally cannot generate invalid JSON.

```python
from vllm import LLM, SamplingParams

sampling_params = SamplingParams(
    temperature=0.7,
    max_tokens=2048,
    guided_json=OptionSetSchema.schema()  # Pydantic schema → JSON Schema
)
```

This makes Step 5 (option generation) reliable without retry logic for schema violations. The model either generates valid structured options or fails at the vllm level — not silently produces malformed JSON.

**Fallback model: Mistral-7B-Instruct-v0.1-GPTQ (4-bit)**

Runs on GTX 1650 via vllm. Same interface, smaller context window (4096), lower quality. Used only when 3090 is unavailable.

**CPU fallback: llama-cpp-python**

```python
from llama_cpp import Llama

llm = Llama(
    model_path="~/.xnch/models/mistral-7b-instruct.Q4_K_M.gguf",
    n_ctx=4096,
    n_threads=16,    # i9 core count
    n_gpu_layers=0   # CPU only in fallback mode
)
```

`llama-cpp-python` is a Python binding over llama.cpp. Single import, no server process needed. Invoked as a library, not a subprocess. Slower (~10 tok/s on i9) but self-contained.

**Integration method: OpenAI-compatible API**

vllm exposes an OpenAI-compatible `/v1/chat/completions` endpoint. The `openai` Python package is used as the HTTP client — not because OpenAI is involved, but because the SDK handles streaming, retries, and timeout correctly, and vllm speaks the same protocol.

```python
from openai import AsyncOpenAI

model_client = AsyncOpenAI(
    base_url="http://localhost:8300/v1",
    api_key="none"  # vllm doesn't require auth in local mode
)

response = await model_client.chat.completions.create(
    model="mistral-7b-instruct",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
    temperature=0.7
)
```

External models (Claude, GPT-4) use the same client pattern with real API keys, accessed only when explicitly configured and network is available. The interface is identical — Nexi's generator.py does not know or care whether it's hitting a local vllm or Anthropic's API. The model URL is config-driven.

---

### 7. Learning Layer

**No model training. No gradient updates. No fine-tuning.**

The learning layer is implemented entirely as: scheduled Python jobs + SQLite queries + versioned weight configs.

**Pattern extraction: `APScheduler`**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(extract_patterns, 'interval', hours=6)
scheduler.add_job(update_weights, 'interval', hours=24)
scheduler.add_job(generate_policy_candidates, 'interval', hours=24)
scheduler.start()
```

APScheduler runs inside the memory-store service process. No separate cron daemon. No Celery. No Redis. The scheduler is async — it doesn't block the FastAPI event loop.

**Pattern extraction job: pure SQL + Python**

```python
async def extract_patterns():
    # Pull unprocessed episodes since last run
    new_episodes = db.execute("""
        SELECT action_type, entity_class, intent_class,
               COUNT(*) as count,
               AVG(CASE WHEN execution_outcome='SUCCESS' THEN 1.0
                        WHEN execution_outcome='PARTIAL' THEN 0.5
                        ELSE 0.0 END) as success_rate,
               json_group_array(context_snapshot) as contexts
        FROM episodes
        WHERE extracted = 0 AND execution_outcome != 'PENDING'
        GROUP BY action_type, entity_class, intent_class
        HAVING count >= 5
    """).fetchall()

    for row in new_episodes:
        confidence = compute_confidence(row.count, row.success_rate)
        upsert_pattern(row, confidence)
        mark_episodes_extracted(row)
```

**Scoring weight adaptation: versioned JSON config**

```json
// ~/.xnch/data/weights_v3.json
{
  "version": "3",
  "created_at": "2026-04-18T10:00:00Z",
  "source_episode_batch": "batch_0042",
  "weights": {
    "EXECUTION": { "policy": 0.25, "outcome": 0.35, "risk": 0.30, "context": 0.10 },
    "QUERY":     { "policy": 0.20, "outcome": 0.25, "risk": 0.15, "context": 0.40 },
    "DECISION":  { "policy": 0.30, "outcome": 0.30, "risk": 0.25, "context": 0.15 }
  }
}
```

Weight update job reads current weights, computes dimension prediction accuracy against last N episodes, adjusts within bounds, writes new versioned file. Nexi loads the latest weight version at session init. Old versions are preserved — weight history is auditable.

**Feedback signal: `prediction_delta` column on episodes**

Every episode records: what outcome_score Nexi predicted vs what actually happened. This delta is the learning signal. Pattern extraction uses it. Weight adaptation uses it. Policy candidate generation uses it. No external ML framework needed — it's subtraction.

---

### 8. Communication Layer

**All inter-service: HTTP/1.1 over localhost via `httpx`**

No gRPC. No message broker. No shared memory. Localhost HTTP is fast enough — sub-millisecond round-trips on loopback. The only bottleneck in this system is model inference (800–3000ms), not HTTP overhead (0.3ms).

`httpx.AsyncClient` with connection pooling:

```python
# Each service gets its own configured client
clients = {
    "xnch": httpx.AsyncClient(
        base_url="http://localhost:8100",
        timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=2.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
    ),
    "model": httpx.AsyncClient(
        base_url="http://localhost:8300",
        timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0)
    )
}
```

**Async outcome delivery: Server-Sent Events (SSE)**

CLI subscribes to `GET /session/{id}/events` on nexi — an SSE stream. Nexi pushes status updates as execution progresses. No polling. No websocket complexity.

```python
from sse_starlette.sse import EventSourceResponse

@router.get("/session/{session_id}/events")
async def session_events(session_id: str):
    async def event_generator():
        while True:
            event = await session_event_queue[session_id].get()
            yield {"data": event.json()}
            if event.is_terminal:
                break
    return EventSourceResponse(event_generator())
```

`sse-starlette` is a single-file FastAPI extension. No additional server config.

**Audit emission: UDP datagrams**

xnch emits high-frequency trace events as UDP to audit-logger:8600. Fire-and-forget. The audit logger buffers and batch-writes to an append-only SQLite table. Critical audit records (verdict issuance, execution tokens) are also written synchronously to the audit table before the response is returned — UDP is for volume, sync write is for guarantee.

```python
import asyncio

audit_transport = None

async def emit_audit_event(event: AuditEvent):
    # Sync write for critical events
    if event.level == AuditLevel.CRITICAL:
        db["audit_log"].insert(event.dict())

    # UDP emit for all events
    if audit_transport:
        audit_transport.sendto(
            event.json().encode(),
            ("127.0.0.1", 8600)
        )
```

---

### 9. Execution Layer

**Action execution: `asyncio.subprocess` + typed handlers**

No Ansible, no Fabric, no shell scripting frameworks. The execution runner is a FastAPI service with a handler registry. Each action type maps to a typed async handler.

```python
HANDLERS: dict[str, Callable] = {
    "SHELL":        ShellHandler(),
    "FILE_WRITE":   FileHandler(),
    "HTTP_REQUEST": HttpHandler(),
    "MODEL_DEPLOY": ModelDeployHandler(),
    "MEMORY_WRITE": MemoryWriteHandler(),
}

async def execute(action: ActionSpec, token: str) -> ExecutionOutcome:
    verify_token(token)   # RS256 verify against public key
    handler = HANDLERS.get(action.type)
    if not handler:
        return ExecutionOutcome(status="FAILURE", reason="Unknown action type")
    return await handler.run(action.spec)
```

Shell execution uses `asyncio.create_subprocess_exec` — not `shell=True`, never `shell=True`. Arguments are passed as a list. No shell injection surface.

```python
async def run(self, spec: ShellSpec) -> ExecutionOutcome:
    proc = await asyncio.create_subprocess_exec(
        *spec.command,          # list, not string
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=spec.working_dir,
        env={**os.environ, **spec.env_overrides}
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(),
        timeout=spec.timeout_seconds
    )
    return ExecutionOutcome(
        status="SUCCESS" if proc.returncode == 0 else "FAILURE",
        stdout=stdout.decode(),
        stderr=stderr.decode(),
        return_code=proc.returncode
    )
```

**Token validation in execution runner:**

```python
from jose import jwt, JWTError

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
        if payload["exp"] < time.time():
            raise ValueError("Token expired")
        return payload
    except JWTError as e:
        raise PermissionError(f"Invalid execution token: {e}")
```

---

### 10. Observability

**Structured logging: `structlog`**

Every service uses structlog with JSON output. Not print statements, not Python's built-in logging with format strings. Structured logs are machine-readable from day one — grepping JSON is trivial, parsing formatted strings is not.

```python
import structlog

log = structlog.get_logger()

log.info("verdict_issued",
    verdict="ALLOW",
    actor_id="pavan",
    action_type="DEPLOY",
    policy_refs=["ml.deploy.gpu_node_only"],
    audit_ref="aud_3b9f",
    latency_ms=28
)
```

Output: `{"event": "verdict_issued", "verdict": "ALLOW", "actor_id": "pavan", ...}`

Log files: one per service at `~/.xnch/logs/{service}.log`. Daily rotation via `logging.handlers.TimedRotatingFileHandler`. 7-day retention.

**Distributed tracing: `trace_id` propagation**

No Jaeger, no OpenTelemetry collector. Trace IDs are UUIDs, propagated as HTTP headers (`X-Trace-ID`) and included in every log line via structlog context binding.

```python
# In nexi, at session start
structlog.contextvars.bind_contextvars(trace_id=request.trace_id)
# All subsequent log calls in this async context include trace_id automatically
```

To trace a full request: `grep trace_id ~/.xnch/logs/*.log | jq 'select(.trace_id=="tr_8a2f")'`

**Audit log: append-only SQLite table in `audit.db`**

```sql
CREATE TABLE audit_log (
    audit_id     TEXT PRIMARY KEY,
    trace_id     TEXT NOT NULL,
    timestamp_ns INTEGER NOT NULL,
    level        TEXT NOT NULL,   -- TRACE | INFO | CRITICAL
    actor_id     TEXT,
    action_type  TEXT,
    verdict      TEXT,
    payload_hash TEXT,
    policy_refs  TEXT,            -- JSON array
    details      TEXT             -- JSON object
) STRICT;
```

`STRICT` table mode: SQLite enforces column types. No type coercion surprises in the audit trail.

**Health endpoints: every service**

```
GET /health → { status, version, uptime_s, dependencies: {name: ok|degraded} }
GET /metrics → { request_count, error_count, p50_latency_ms, p99_latency_ms }
```

No Prometheus exposition format for v0. Simple JSON endpoints, queryable with curl. Metrics are in-memory counters, reset on restart. Add Prometheus exporter in v1 if needed.

---

### 11. Performance & Concurrency

**Model calls: single concurrent, no queue on day one**

Single-user system. One model request at a time. vllm handles its own KV cache and batching internally. Nexi's generator.py holds a semaphore:

```python
model_semaphore = asyncio.Semaphore(1)

async def generate_options(prompt: str) -> list[Option]:
    async with model_semaphore:
        return await _call_model(prompt)
```

If a second session starts (shouldn't happen, CLI is blocking), it waits on the semaphore. No queue, no timeout on the semaphore wait — the CLI blocks until the model is free.

**Policy dry-runs: fully parallel**

```python
async def filter_by_policy(options: list[Option], manifest: ContextManifest):
    tasks = [check_policy(opt, manifest) for opt in options]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return process_verdicts(options, results)
```

5 concurrent HTTP calls to xnch. xnch handles them with FastAPI's async route handlers. SQLite reads are non-blocking under WAL mode. No contention.

**SQLite write serialization: `asyncio.Lock` per database**

SQLite allows one writer at a time under WAL. Rather than relying on SQLite's own write serialization (which raises `OperationalError: database is locked` under contention), each database gets an asyncio.Lock:

```python
episodic_write_lock = asyncio.Lock()

async def write_episode(episode: Episode):
    async with episodic_write_lock:
        db["episodes"].insert(episode.dict(), pk="episode_id")
```

Reads don't take the lock — WAL allows concurrent reads alongside a write.

**Memory manifests: short TTL cache**

```python
from functools import lru_cache
import time

_manifest_cache: dict[str, tuple[float, ContextManifest]] = {}
MANIFEST_TTL = 60.0  # seconds

async def load_context(intent: Intent) -> ContextManifest:
    cache_key = f"{intent.entity_id}:{intent.intent_class}"
    if cache_key in _manifest_cache:
        ts, manifest = _manifest_cache[cache_key]
        if time.time() - ts < MANIFEST_TTL:
            return manifest
    manifest = await fetch_manifest_from_xnch(intent)
    _manifest_cache[cache_key] = (time.time(), manifest)
    return manifest
```

Reduces repeated SQLite reads for the same entity within a short window. 60-second TTL — stale enough to avoid thrashing, fresh enough to reflect recent memory updates.

---

### 12. Deployment Model

**Process manager: `supervisord`**

Not systemd (too much config for dev). Not PM2 (Node.js ecosystem). supervisord is a Python process manager — single config file, process restart on crash, log aggregation, and a simple CLI to start/stop/restart individual services.

```ini
; ~/.xnch/supervisord.conf
[supervisord]
logfile=~/.xnch/logs/supervisord.log

[program:memory-store]
command=~/.xnch/venv/bin/uvicorn memory.api:app --port 8400 --workers 1
directory=~/xnch-system
autostart=true
autorestart=true
stdout_logfile=~/.xnch/logs/memory.log

[program:xnch-server]
command=~/.xnch/venv/bin/uvicorn xnch.main:app --port 8100 --workers 1
directory=~/xnch-system
autostart=true
autorestart=true
depends_on=memory-store
stdout_logfile=~/.xnch/logs/xnch.log

[program:nexi-engine]
command=~/.xnch/venv/bin/uvicorn nexi.main:app --port 8200 --workers 1
directory=~/xnch-system
autostart=true
autorestart=true
depends_on=xnch-server
stdout_logfile=~/.xnch/logs/nexi.log

[program:execution-runner]
command=~/.xnch/venv/bin/uvicorn execution.runner:app --port 8500 --workers 1
directory=~/xnch-system
autostart=true
autorestart=true
stdout_logfile=~/.xnch/logs/execution.log

[program:vllm-primary]
command=~/.xnch/venv/bin/vllm serve mistralai/Mistral-7B-Instruct-v0.3
        --port 8300 --gpu-memory-utilization 0.75 --max-model-len 8192
directory=~/xnch-system
autostart=true
autorestart=true
stdout_logfile=~/.xnch/logs/vllm.log
environment=CUDA_VISIBLE_DEVICES="0"
```

```bash
# Start everything
supervisord -c ~/.xnch/supervisord.conf

# Control individual services
supervisorctl restart nexi-engine
supervisorctl status
supervisorctl tail -f xnch-server
```

vllm starts last — other services are healthy before model loads. supervisord handles restart on crash automatically.

---

### Minimal Dependency List

```toml
# pyproject.toml (shared)
[tool.poetry.dependencies]
python = "^3.11"

# Core framework
fastapi = "^0.111"
uvicorn = {extras = ["standard"], version = "^0.29"}
pydantic = "^2.7"
typer = {extras = ["all"], version = "^0.12"}

# HTTP client
httpx = "^0.27"

# Storage
sqlite-utils = "^3.36"
sqlite-vec = "^0.1"             # vector search in SQLite

# Model integration
openai = "^1.30"                # vllm-compatible client
llama-cpp-python = "^0.2"       # CPU fallback
sentence-transformers = "^3.0"  # embeddings for semantic similarity

# Auth / tokens
python-jose = {extras = ["cryptography"], version = "^3.3"}

# Scheduling (learning layer)
apscheduler = "^3.10"

# Logging
structlog = "^24.1"

# SSE (async event streaming)
sse-starlette = "^2.1"

# Policy engine (phase 2)
# python-opa-client = "^0.3"   # uncomment when OPA integration begins

# Development only
pytest = "^8.0"
pytest-asyncio = "^0.23"
httpx = "^0.27"                 # for TestClient in tests
```

**Runtime dependencies (not Python packages):**
```
vllm           — pip install vllm (installs with CUDA support)
supervisord    — pip install supervisor
OPA binary     — single static binary, wget on demand (phase 2)
SQLite 3.38+   — ships with Python 3.11
```

**Total pip-installable packages: 12 core, 3 dev.** Everything else is standard library.

---

### Folder Structure

```
~/xnch-system/
│
├── shared/                     # Cross-service utilities
│   ├── config.py               # Loads ~/.xnch/config.yaml, exposes typed config
│   ├── schema.py               # All Pydantic models used across services
│   ├── tokens.py               # JWT sign/verify, uses ~/.xnch/keys/
│   ├── db.py                   # SQLite connection factory + pragma setup
│   ├── migrations/             # Versioned schema migrations
│   │   ├── __init__.py
│   │   ├── v1_initial.py
│   │   └── v2_add_prediction_delta.py
│   └── logging.py              # structlog configuration, trace_id binding
│
├── xnch/                       # Control plane service (port 8100)
│   ├── main.py                 # FastAPI app, lifespan, router registration
│   ├── session.py              # /session/init, actor resolution
│   ├── policy_engine.py        # YAML policy loader + rule evaluator
│   ├── governance.py           # RBAC, role → capability resolution
│   ├── verdict.py              # /verdict endpoint, token issuance
│   ├── policy_check.py         # /policy/check dry-run endpoint
│   ├── execution_gate.py       # /execution/outcome receiver
│   ├── memory_proxy.py         # /memory/read, /memory/write (proxies to memory-store)
│   └── audit.py                # Sync + UDP audit emission
│
├── nexi/                       # Decision engine (port 8200)
│   ├── main.py                 # FastAPI app, session router
│   ├── session.py              # Session lifecycle, SSE event queue
│   ├── intent.py               # Intent interpretation, ambiguity scoring
│   ├── context.py              # Context manifest loading, manifest pinning
│   ├── generator.py            # Model calls, schema validation, fallback chain
│   ├── policy_filter.py        # Parallel /policy/check, verdict processing
│   ├── evaluator.py            # Option scoring, weight application
│   ├── simulator.py            # Outcome simulation (conditional)
│   ├── selector.py             # Decision record assembly, selection
│   └── callbacks.py            # /callback/outcome receiver, memory write trigger
│
├── memory/                     # Memory store service (port 8400)
│   ├── main.py                 # FastAPI app
│   ├── api.py                  # /memory/read, /memory/write, /pattern/update
│   ├── episodic.py             # Episodes table: CRUD + time-range queries
│   ├── semantic.py             # Patterns table: upsert, confidence query
│   ├── policy_store.py         # Policy file watcher + version tracking
│   ├── vectors.py              # sqlite-vec operations, embedding storage
│   └── learning/
│       ├── extractor.py        # Pattern extraction job (APScheduler)
│       ├── weight_optimizer.py # Scoring weight adaptation job
│       └── policy_candidate.py # Derived policy generation job
│
├── execution/                  # Execution runner (port 8500)
│   ├── main.py                 # FastAPI app
│   ├── runner.py               # /execute endpoint, token verify, handler dispatch
│   ├── outcome.py              # POST to xnch /execution/outcome
│   └── handlers/
│       ├── shell.py            # asyncio subprocess, no shell=True
│       ├── file.py             # File system operations
│       ├── http.py             # Outbound HTTP actions
│       └── model.py            # vllm model management actions
│
├── audit/                      # Audit logger (port 8600 UDP)
│   ├── logger.py               # UDP listener, batch writer
│   └── query.py                # /audit/query endpoint for forensic access
│
├── cli/                        # Command-line interface
│   ├── main.py                 # Typer app, entry point
│   ├── session.py              # Session initiation, SSE subscription
│   ├── display.py              # Rich terminal output (reasoning trace, status)
│   └── config.py               # CLI config (server URLs, auth token)
│
├── tests/
│   ├── unit/
│   │   ├── test_policy_engine.py
│   │   ├── test_evaluator.py
│   │   └── test_token.py
│   ├── integration/
│   │   ├── test_verdict_flow.py
│   │   └── test_session_e2e.py
│   └── conftest.py             # Shared fixtures, test DB setup
│
├── scripts/
│   ├── init.sh                 # First-run setup: dirs, keys, DB init
│   ├── start.sh                # supervisord start
│   ├── stop.sh                 # supervisord stop
│   └── rebuild_semantic.py     # Manual semantic DB rebuild from episodic
│
~/.xnch/                        # Runtime data (outside source tree)
├── config.yaml
├── supervisord.conf
├── keys/
│   ├── private.pem
│   └── public.pem
├── data/
│   ├── episodic.db
│   ├── semantic.db
│   ├── policy.db
│   └── audit.db
├── policies/
│   ├── defaults.yaml
│   ├── ml_deploy.yaml
│   └── infra.yaml
├── weights/
│   └── weights_v1.json
├── models/
│   └── mistral-7b-instruct.Q4_K_M.gguf
└── logs/
    ├── supervisord.log
    ├── xnch.log
    ├── nexi.log
    ├── memory.log
    ├── execution.log
    └── vllm.log
```

**How everything fits together in one sentence:** FastAPI services communicate over localhost HTTP via httpx async clients, share Pydantic schemas from `shared/schema.py`, read config from `shared/config.py`, write structured logs via structlog with trace ID propagation, persist all state to SQLite databases in `~/.xnch/data/`, and are managed as processes by supervisord — with vllm on the 3090 as the only GPU-bound component, callable via the OpenAI-compatible client from any service that needs generation.