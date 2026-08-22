# xnch: Control-Plane Role vs nexi

`xnch` is the **governance, memory, and authorization control plane**.
`nexi` (the sibling submodule) is the **execution engine** that runs the
decision pipeline. xnch owns authority; nexi owns computation.

```
 Input ──► xnch (/session/init, /nexi/chat)      "transport + auth + dedup"
              │  forward SessionContext
              ▼
          nexi (/session/start)                  "intent → context → options"
              │  Step 4: POST /memory/read       xnch returns ContextManifest
              │  Step 6: /policy/check           xnch dry-runs each option
              │  Step 10: /verdict               xnch re-evaluates + signs token
              ▼
          executor ──► POST /execution/execute, /execution/outcome  (xnch)
              │         xnch records episode + fires nexi /callback/outcome
              ▼
          xnch (/nexi/memory/recall, /memory/graph/*)   long-term memory & L3 graph
```

## Division of responsibility

| Concern | Owned by | xnch surface |
|---------|----------|--------------|
| Actor identity, roles, capabilities | xnch | `/auth/*`, `/governance/actors`, SQLite `actors` table (bootstrap: admin, operator, viewer, agent) |
| Session transport, dedup, rate-limit | xnch | `/session/init`, `/session/{id}/clarify`, `/v1/chat/completions` |
| Context manifest assembly (memory read) | xnch | `/memory/read` |
| Policy evaluation (dry-run + authoritative) | xnch | `/policy/check`, `/verdict` |
| Execution-token issuance (RS256) + jti replay protection | xnch | `/verdict` → `execution_token`; public key at `/auth/public-key` |
| Decision/episode ledger + audit events | xnch | `/verdict`, `/execution/outcome`, audit JSONL under `XNCH_BASE_DIR` |
| Long-term memory, patterns, L3 semantic graph | xnch | `/memory/write`, `/memory/recall` (via nexi), `/memory/graph/*`, SSE stream |
| Intent interpretation, context loading, option generation, evaluation, selection, plan compilation | nexi | consumes xnch `/memory/read` + `/policy/check` through `nexi/adapters/xnch_client.py` |
| Execution dispatch | nexi (via executor) | xnch records outcome and calls back to nexi `/callback/outcome` |
| HITL approval gate for EXECUTION (LangGraph) | xnch (optional) | `/governance/pipeline/invoke`, `/resume`, `/pipeline/{thread_id}` when `XNCH_LANGGRAPH_PIPELINE=true` |
| MCP tool federation for the runtime | xnch | `/mcp/*`, `/nexi/tools` (bridged servers) |
| Voice STT/TTS | xnch | `/nexi/voice/*` |

## The two pipeline shapes

1. **Classic HTTP pipeline (default).** The nexi engine drives the loop and
   calls back into xnch at each step (`/memory/read`, `/policy/check`,
   `/verdict`). xnch never runs the graph; it is a stateless-enough authority
   over stateful stores.

2. **LangGraph HITL pipeline (feature-flagged).** When `XNCH_LANGGRAPH_PIPELINE=true`,
   xnch runs the compiled decision graph in-process
   (`xnch/agents/pipeline_graph.py` + `PipelineRuntime` in
   `xnch/agents/pipeline_runtime.py`), backed by an `AsyncPostgresSaver`
   checkpointer. EXECUTION selects call `interrupt()` and wait for a human
   approve/reject via `/governance/pipeline/resume`. Graph nodes still delegate
   to the same nexi modules (`intent_interpreter`, `context_loader`,
   `option_generator`, `policy_filter`, `evaluator`, `selector`,
   `plan_compiler`), so both shapes share logic — they differ in *who hosts the
   loop* and *where human approval is inserted*.

## Auth model (v0)

Two token systems:

| Token | Direction | Algorithm | Purpose |
|-------|-----------|-----------|---------|
| Actor token / actor reference | caller → xnch | HS256 (`XNCH_AUTH_SECRET`) or literal `actor:<id>` (dev) | Prove actor identity for `/session/*`, `/verdict`, `/v1/chat/completions` |
| Execution token | xnch → executor | RS256 (keypair in `XNCH_BASE_DIR/keys`) | Authorize a single governed action; jti replay-protected; TTL by trust level |

`TokenVerifier.verify_bearer()` (xnch/auth/token.py) accepts:
- `actor:<actor_id>` — dev shortcut, returns the id verbatim
- `Bearer <hs256-jwt>` — `sub` claim is the actor id

Trust levels map actor roles to execution-token TTLs
(`xnch/security/trust_model.py`):

| Role | Trust level | Token TTL |
|------|-------------|-----------|
| `nexi` | SYSTEM | 7 days |
| `admin`, `operator` | OWNER | 1 day |
| `agent`, `opencode`, `perception_daemon`, `consolidation_job` | TRUSTED_AGENT | 1 hour |
| `viewer` | EXTERNAL_AGENT | 30 min |
| `external` (default) | UNTRUSTED | no token (0) |

## Stores that shape API behavior

| Store | Backend | Affects |
|-------|---------|---------|
| `GovernanceStore` | SQLite (`xnch.db`, `actors`) | `/verdict` 401s, `/session/init` actor resolution, `/governance/actors` |
| `EpisodicStore` (SQLite) + `PgEpisodicStore` (pgvector) | SQLite + PostgreSQL | `/memory/read`, `/memory/write`, `/execution/outcome`, `/nexi/memory/recall` |
| `PatternStore`, `KVCache` | SQLite + Redis | `/memory/read` patterns, `/session/init` dedup/rate-limit, `/governance/weights` |
| `GraphStore` (Kuzu) + `RelationshipStore` (PG) | Kuzu + PostgreSQL | `/memory/graph/*`, SSE stream, `/nexi/system-prompt` entity feed |
| `EventLog`, `DecisionLedger` | JSONL under `XNCH_BASE_DIR/audit` | audit events emitted by most routes |
| `PipelineRuntime` | LangGraph + AsyncPostgresSaver | `/governance/pipeline/*` (only when runtime ready) |

## Nexi callbacks xnch fires

- `POST {nexi_base_url}/session/start` — from `/session/init`, `/session/{id}/clarify`, `/v1/chat/completions` (forward the SessionContext).
- `POST {nexi_base_url}/callback/outcome` — from `/execution/outcome` (fire-and-forget with `outcome_score_predicted`).
