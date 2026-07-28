# XNCH/Nexi — Full End-to-End Architecture Plan

## Context

The `rearchitecture-discussion.md` document defines the complete cognitive architecture vision for the system. The current codebase implements a solid ~65% of the governance/decision core, but is missing the routing layer, the evolved 4-layer memory system, perception pipeline, observability, infrastructure manifests, and the product interface layer. This plan maps the vision to the existing code and sequences the work needed to get from here to a fully running system.

**One critical naming collision to resolve upfront:**

| Discussion term | Meaning | Code equivalent |
|---|---|---|
| XNCH | Full platform: routing + memory + perception + observability | `xnch/` service + LiteLLM + XnchMemory + perception daemons |
| Nexi | Product face: personality + interface + messaging | OpenClaw (borrowed) wired to XNCH |
| (no discussion term) | Decision/policy pipeline | Current `nexi/` service — rename conceptually to **xnch-engine** or keep as internal service |

The code's `nexi/` service is part of the XNCH platform. The discussion's "Nexi" is OpenClaw pointing at XNCH. These are different things with the same name. The plan keeps the directory names unchanged but tracks this distinction in design.

---

## Current State Assessment

### What's solid (don't touch)
- `xnch/auth/` — JWT HS256, replay protection, actor role registry ✓
- `xnch/memory/kv_cache.py` — Redis dedup + rate limiting ✓
- `xnch/memory/episodic_store.py` / `pattern_store.py` — SQLite CRUD ✓
- `xnch/audit/` — JSONL ledger + event log ✓
- `xnch/policy/engine.py` + `loader.py` — first-match rule evaluation ✓
- `xnch/routes/` — all 9 endpoints exist and work ✓
- `nexi/adapters/` — xnch_client + model_adapter ✓
- `nexi/pipeline/evaluator.py` + `selector.py` ✓
- All existing tests (31 test files, ~40k lines) ✓

### What's broken (must fix before building more)
Four critical gaps from `ArchitecturalAuditReport.md`:
- **C-1**: Scoring dimension name schism (code uses `policy_score/outcome_score/risk_score/context_fit_score`; audit schema uses `safety/efficiency/compliance/context_fit` — reconcile to one name set)
- **C-2**: DAG schema undefined — `plan_compiler.py` is a stub, no DAG contract
- **C-3**: Policy DSL examples use `DENY` verdict which doesn't exist in enum (only ALLOW/ALLOW_WITH_WARNINGS/MODIFY/DEFER/BLOCK)
- **C-4**: Pattern extractor grouping tuple defined inconsistently across 3 documents

### What's stubbed (needs real implementation)
- `nexi/pipeline/intent_interpreter.py` — raises `ClarificationRequired`, no real parsing
- `nexi/pipeline/option_generator.py` — skeleton LLM call
- `nexi/pipeline/plan_compiler.py` — validates action_spec exists, nothing more
- `xnch/learning/pattern_extractor.py`, `score_adapter.py`, `policy_candidates.py` — all stubs

### What doesn't exist yet
- LiteLLM routing proxy
- Gemma 4 26B model config (current: Mistral-7B-Instruct-v0.3)
- XnchMemory layer 2 (PostgreSQL + pgvector) — currently SQLite
- XnchMemory layer 3 (Kuzu semantic graph)
- Decay scoring on memories
- Perception pipeline (VAD, Whisper, Moondream, file watcher)
- OpenClaw interface layer
- Langfuse observability
- Mem0 / Zep memory middleware
- k8s manifests, Dockerfiles, Helm charts
- Nightly consolidation CronJob

---

## Hardware Assignment

```
i7 (GTX 1650 4GB, 16GB RAM) — Memory Node
  Redis     Layer 0 sensory buffer + Layer 1 working memory
  PostgreSQL + pgvector    Layer 2 episodic store
  Kuzu      Layer 3 semantic graph
  LiteLLM   XNCH routing proxy (CPU-only)
  Langfuse  Observability
  xnch/     Control plane service
  Perception daemons (Whisper, Moondream on GTX 1650)

i9 (RTX 3090 24GB, 48GB RAM) — Inference Node
  vLLM + Gemma 4 26B    Primary model (RTX 3090)
  nexi/     Decision engine service
  Mem0 sidecar          Memory middleware (stateless, data on i7)
  Zep sidecar           Entity extraction middleware
  OpenClaw gateway      Nexi interface layer
```

---

## Phased Implementation Plan

### Phase 0 — Fix Critical Gaps (prerequisite for everything)

**Files to change:**

1. **Scoring dimension names** — pick one naming scheme and apply everywhere:
   - Chosen canonical names: `policy_score`, `outcome_score`, `risk_score`, `context_fit_score` (matches code and weight config schema)
   - Update `docs/` audit.md and learning-loop.md to use these names
   - Update `xnch/learning/score_adapter.py` monitoring config keys
   - Update `xnch/audit/ledger.py` `dimension_scores` field names
   - Update any references in `xnch/routes/verdict.py`

2. **DAG schema** — define a concrete execution DAG contract:
   - Add `CompiledDAG` Pydantic model: `nodes: list[DAGNode]`, `edges: list[tuple[str,str]]`, `entry_node: str`
   - Add `DAGNode`: `node_id`, `action_type`, `target`, `params`, `depends_on: list[str]`
   - Add to `nexi/models/` (new file: `dag.py`)
   - Implement `nexi/pipeline/plan_compiler.py` to convert `action_spec` → `CompiledDAG` (single-node DAG for now, multi-node later)

3. **DENY verdict** — fix policy DSL examples:
   - Search `policies/` and `docs/` for `DENY`, replace with `BLOCK`

4. **Pattern extractor tuple** — canonicalize:
   - Canonical: `(intent_class, action_type, entity_class, actor_role)` in that order
   - Update all three conflicting doc references and align `xnch/learning/pattern_extractor.py`

**Tests**: Run `pytest` to confirm all existing tests pass before proceeding.

---

### Phase 1 — XnchMemory Evolution (layer 2 + layer 3 + decay)

The discussion's 4-layer memory architecture. Layers 0 and 1 already exist (Redis in `kv_cache.py`). Need layers 2 and 3.

**Layer 2 — PostgreSQL + pgvector (replace SQLite episodic store)**

- New file: `xnch/memory/pg_episodic_store.py`
  - Mirrors `episodic_store.py` interface but uses asyncpg + pgvector
  - Schema: `memory` table with columns matching discussion spec:
    `id, timestamp, type, raw_text, summary, embedding (vector), importance (float), recall_count, last_recalled, decay_score`
  - `decay_score` computed column: `importance × recency_factor × (1 + 0.1 × recall_count)`
  - Index: `CREATE INDEX ON memory USING ivfflat (embedding vector_cosine_ops)`
  - Retrieval: hybrid — keyword filter (SQL `WHERE`) + semantic similarity (`<=>` operator)
  - Update `xnch/main.py` lifespan to init pg pool alongside SQLite (migration path: keep SQLite for patterns, move episodes to pg)
  - Add `POSTGRES_URL` to `xnch/config.py`

- Reuse: existing `episodic_store.py` interface contract — same method signatures, new backend

**Layer 3 — Kuzu semantic graph (entity + relationship store)**

- New file: `xnch/memory/graph_store.py`
  - Kuzu embedded (in-process, no server) at `~/.xnch/graph/`
  - Schema: `CREATE NODE TABLE Entity(id STRING, name STRING, type STRING, PRIMARY KEY(id))`
  - Schema: `CREATE REL TABLE Relation(FROM Entity TO Entity, rel_type STRING, confidence FLOAT)`
  - Methods: `upsert_entity`, `upsert_relation`, `query_entity_connections`, `get_entity_by_name`
  - No server needed — Kuzu is embedded like SQLite

- New file: `xnch/memory/graph_extractor.py`
  - Reads recent episodes from PostgreSQL layer 2
  - Calls small LLM (via LiteLLM, Phi-3 on i7 GTX 1650) to extract entity/relation triples
  - Writes to Kuzu via `graph_store.py`
  - Called by nightly CronJob (not a daemon)

**Decay scoring + recall strengthening**

- Add `bump_recall` method to `pg_episodic_store.py`: increments `recall_count`, updates `last_recalled`, recomputes `decay_score`
- Call `bump_recall` in `xnch/routes/memory.py` after every successful `/memory/read` retrieval

**Nightly consolidation**

- New file: `xnch/jobs/consolidation.py`
  - Step 1: Zep summarization call — compress yesterday's episodes into facts
  - Step 2: `graph_extractor.py` run — extract entities → Kuzu
  - Step 3: Decay score recomputation for all memories
  - Step 4: Archive memories below decay threshold (set `archived=True`, don't delete)
- Registered as k8s `CronJob` (see Phase 6), schedule: `0 2 * * *` (2 AM daily)

---

### Phase 2 — LiteLLM Routing Layer

This becomes XNCH's routing brain — replaces direct vLLM calls in `nexi/adapters/model_adapter.py`.

**LiteLLM config file** (new: `xnch/litellm_config.yaml`)
```yaml
model_list:
  - model_name: gemma4-local
    litellm_params:
      model: ollama/gemma4:26b
      api_base: http://i9-node:11434

  - model_name: claude-judgment
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: phi3-encoder
    litellm_params:
      model: ollama/phi3:mini
      api_base: http://i7-node:11434

router_settings:
  routing_strategy: usage-based-routing
  fallbacks:
    - gemma4-local: [claude-judgment]
```

**Routing decision logic** — new file: `xnch/routing/classifier.py`
- `classify_request(raw_input, actor_role, metadata) → ModelRoute`
- Rules (in priority order):
  1. `privacy_sensitive` flag set → `gemma4-local` only
  2. `intent_class == EXECUTION` → `gemma4-local` (code tasks, local)
  3. `intent_class == DECISION` and `complexity_score > 0.7` → `claude-judgment`
  4. default → `gemma4-local`
- Called in `nexi/adapters/model_adapter.py` before every LLM call

**Update nexi model adapter** (`nexi/adapters/model_adapter.py`)
- Replace direct vLLM URL with LiteLLM proxy URL: `http://i7-node:4000/v1`
- Add `model` param from classifier output
- Update `nexi/config.py`: `litellm_base_url=http://localhost:4000`

---

### Phase 3 — Intent Interpreter (stub → real)

The biggest stubbed component in the decision pipeline.

**File: `nexi/pipeline/intent_interpreter.py`** (implement)
- Use LiteLLM (via model_adapter) with structured output (Pydantic `Intent` model)
- Prompt: system prompt defines `IntentClass` enum + structured extraction schema
- Output: `Intent(intent_class, action_type, entity_class, urgency, raw_input, clarifications_needed)`
- If `clarifications_needed` non-empty → raise `ClarificationRequired` with questions (existing behavior preserved)
- Reuse existing `Intent` model from `nexi/models/`

**File: `nexi/pipeline/option_generator.py`** (implement)
- Generate N=5 `PlanOption` objects via LLM
- System prompt: role + available actions + intent
- Structured output: list of `PlanOption` objects
- Reuse `nexi/config.py` `options_count` setting

---

### Phase 4 — Perception Pipeline (i7 / GTX 1650)

Event-driven, not daemon. Two real daemons, everything else is triggered.

**Voice perception** — new: `xnch/perception/voice_daemon.py`
- Silero VAD (CPU, i7) + faster-whisper (GTX 1650)
- Phase 1: push-to-talk mode (triggered by signal/API call)
- Phase 2: always-on VAD loop (future)
- On transcript ready: write to Redis Layer 0 with TTL=60s key: `perception:voice:{uuid}`
- Triggers attention filter

**Visual perception** — new: `xnch/perception/vision_encoder.py`
- Moondream 2 (GTX 1650, ~2GB VRAM)
- Called on-demand at query time (not always-on in Phase 1)
- Input: screenshot bytes → Output: text description
- Writes to Redis Layer 0

**File watcher** — new: `xnch/perception/file_watcher.py`
- Uses `watchdog` library (lightweight inotify wrapper)
- Watches `~/.xnch/vault/` (Obsidian vault mount point)
- On change: triggers vault indexer Job via k8s Job API

**Attention filter** — new: `xnch/perception/attention_filter.py`
- Rule-based (Phase 1):
  - Voice transcript present + silence > 1.5s → forward to XNCH gateway
  - Screen change > pixel diff threshold → encode + store Layer 2
  - File saved in vault → trigger indexer
  - User idle > 10 min → trigger memory consolidation, suppress responses
- Phase 2: River online ML classifier

---

### Phase 5 — Observability (Langfuse + existing Prometheus)

**Langfuse integration** — new: `xnch/observability/langfuse_client.py`
- Wraps every LLM call with Langfuse trace
- `trace_llm_call(prompt, response, model, latency_ms, tokens_used)`
- Reuse existing `xnch/audit/event_log.py` pattern — emit events that also go to Langfuse
- Add `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` to `xnch/config.py`

**Wire into existing pipeline**
- `nexi/adapters/model_adapter.py`: wrap every `_call_model` with Langfuse span
- `xnch/routes/verdict.py`: emit trace on every verdict
- Reuse `xnch/audit/event_log.py` emit pattern — don't duplicate

---

### Phase 6 — OpenClaw Interface Layer (Nexi product face)

Wire OpenClaw to XNCH — 1 config change, Nexi is live.

**OpenClaw config** (`~/.openclaw/config.yaml`):
```yaml
model:
  provider: custom
  base_url: http://i7-node:4000   # LiteLLM gateway
  api_key: ${LITELLM_API_KEY}
  model: gemma4-local

persona:
  name: Nexi
  system_prompt: |
    You are Nexi, a private AI assistant running entirely on local hardware.
    You have persistent memory across sessions. You are direct, technically precise,
    and proactive. You address the user as ck-san.
```

**Memory middleware bridge**
- Deploy Mem0 on i9, backend pointing to i7 PostgreSQL (layer 2)
- Deploy Zep on i9, entity extraction feeds into Kuzu (layer 3)
- OpenClaw's built-in memory → replaced by Mem0 bridge over time

**SKILL.md adoption** — new: `xnch/skills/`
- Define each XNCH tool capability as a `SKILL.md` file
- Format: compatible with `agentskills.io` standard (same format as Hermes Agent)
- Initial skills: `memory_search.md`, `vault_query.md`, `code_execute.md`

---

### Phase 7 — Learning Loop (stubs → implementation)

**`xnch/learning/pattern_extractor.py`** (implement)
- Query `pg_episodic_store` for episodes since last extraction run
- Group by `(intent_class, action_type, entity_class, actor_role)` — canonical tuple
- Compute `success_rate`, `confidence`, `observation_count` per group
- Upsert into `pattern_store.py`
- Scheduled every 6h (already registered in `xnch/main.py` scheduler)

**`xnch/learning/score_adapter.py`** (implement)
- Monitor per-dimension accuracy using canonical dimension names (`policy_score` etc.)
- Detect drift: rolling 7-day accuracy vs. 30-day baseline
- If drift > threshold: call `/governance/weights/propose` with updated config
- Scheduled every 6h30m (already registered)

**`xnch/learning/policy_candidates.py`** (implement)
- Read `pattern_store` for low success patterns
- LLM call: "given these failure patterns, suggest policy rule candidates"
- Output: candidate rules in policy DSL format
- Write to `pending_candidates` table (already in SQLite schema)

**Hermes MLOps pipeline** (Phase 3 / future)
- Capture every LLM interaction as trajectory (input → tool calls → output)
- Export in ShareGPT format via Hermes Agent's pipeline
- Use for fine-tuning Gemma 4 on XNCH-specific patterns

---

### Phase 8 — Infrastructure (k8s Manifests + Dockerfiles)

**New directory: `deploy/`**

```
deploy/
├── docker/
│   ├── xnch.Dockerfile
│   └── nexi.Dockerfile
├── k8s/
│   ├── namespaces.yaml
│   ├── i7-node/
│   │   ├── redis.yaml
│   │   ├── postgres-pgvector.yaml
│   │   ├── kuzu-service.yaml
│   │   ├── langfuse.yaml
│   │   ├── xnch-deployment.yaml
│   │   ├── litellm-deployment.yaml
│   │   └── perception-daemonset.yaml
│   ├── i9-node/
│   │   ├── vllm-gemma4.yaml
│   │   ├── nexi-deployment.yaml
│   │   ├── mem0-deployment.yaml
│   │   └── zep-deployment.yaml
│   └── jobs/
│       ├── consolidation-cronjob.yaml     # 0 2 * * *
│       └── vault-indexer-job.yaml         # triggered by file watcher
└── helm/
    └── xnch-stack/                        # future
```

**Node labeling**:
```bash
kubectl label node i7-node role=memory
kubectl label node i9-node role=inference
```

**Resource budgets (i7 — 16GB RAM)**:

| Service | RAM request | RAM limit | CPU | Notes |
|---|---|---|---|---|
| System + k8s | 2GB | 2GB | 2 | reserved |
| xnch | 1GB | 1.5GB | 1 | |
| LiteLLM | 512MB | 1GB | 1 | |
| Redis | 1GB | 2GB | 0.5 | |
| PostgreSQL+pgvector | 3GB | 5GB | 3 | |
| Kuzu (embedded in xnch) | 0 | — | — | embedded |
| Langfuse | 1GB | 1.5GB | 1 | |
| Perception (whisper+moondream) | 2GB | 3GB | 1 | GTX1650 GPU |
| Headroom | ~2GB | — | — | |

**Resource budgets (i9 — 48GB RAM)**:

| Service | RAM | GPU | Notes |
|---|---|---|---|
| System + k8s | 2GB | — | |
| nexi (decision engine) | 2GB | — | |
| vLLM + Gemma 4 26B | 20GB | RTX 3090 18GB VRAM | Q4_K_M quant |
| Mem0 | 512MB | — | stateless, data on i7 |
| Zep | 1GB | — | stateless |
| OpenClaw gateway | 512MB | — | |
| Headroom | ~22GB | 6GB VRAM | future vision model |

---

## Execution Sequence

```
Phase 0  Fix critical gaps (C-1 through C-4)           1-2 days
Phase 1  XnchMemory layer 2 (pgvector) + layer 3 (Kuzu) 3-5 days
Phase 2  LiteLLM routing + Gemma 4 config               1-2 days
Phase 3  Intent interpreter + option generator (real)    2-3 days
Phase 6  OpenClaw wired to LiteLLM → Nexi is live       1 day
Phase 5  Langfuse observability                          1 day
Phase 4  Perception pipeline (voice first)               3-5 days
Phase 7  Learning loop implementation                    3-5 days
Phase 8  k8s manifests + Dockerfiles                    3-5 days
```

Start with Phase 0 → Phase 1 → Phase 2 → Phase 6. After Phase 6, Nexi is live and usable. Everything after is progressive enhancement.

---

## Verification

**Phase 0**: `pytest` — all existing tests green. No DENY in policy files. `grep` confirms one naming scheme.

**Phase 1**: PostgreSQL query returns episodic memories with vector similarity. Kuzu `MATCH` query returns entity connections. `decay_score` decreases over time, increases on recall.

**Phase 2**: `curl http://i7-node:4000/v1/models` lists gemma4-local and claude-judgment. `curl -d '{"model":"gemma4-local",...}'` returns response from i9 Gemma 4.

**Phase 3**: `pytest nexi/tests/test_session_flow.py` — intent interpreter returns structured `Intent` with `intent_class` populated. No more stub `ClarificationRequired` on basic inputs.

**Phase 6**: Send "hello" on Telegram → Nexi responds via OpenClaw → Langfuse shows trace → Mem0 stores memory → next session recalls it.

**Phase 8**: `kubectl get pods -A` — all services Running. `kubectl top nodes` — i7 under 14GB, i9 under 26GB.
