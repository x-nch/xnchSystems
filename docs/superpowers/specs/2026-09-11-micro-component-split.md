# xnchSystems Micro-Component Split — Plan, Specs & Tasks

**Date:** 2026-09-11
**Status:** Approved direction (Approach A) — pending implementation
**Approach:** Consolidate-then-extract (hybrid)
**Scope:** xnchSystems superrepo (`xnch/`, `nexi/`, `xnch_mcp/`, `exec_agent/`, `fs_read_agent/`, `agent-runner/`, `cli/`, `scraper/`, `infra/no-k3s/`)

---

## 1. Executive Summary

xnchSystems has accumulated four classes of redundancy: two parallel memory systems, four top-level runner/agent directories, policy logic perceived as triplicated, and execution concerns split across both services. This document specifies a **hybrid reorganization**:

- **Phase 1 — Consolidation (no new services):** merge the two capability sidecars into one, collapse the `xnch_mcp` exec/fs double-layer, formally assign single homes to policy and memory concerns, and group client tooling.
- **Phase 2 — Extraction (one new service):** extract `xnch/memory` into an independently deployable **memory-service**, following the existing `perception.service` precedent.
- **Phase 3 — Verification:** contract tests, observability, docs.

**All external contracts stay stable** (`am_*` MCP tools, `xnch_*` MCP tools, web UI, chat API, agent-runner dispatch). Result: ~7 app-level deployables, within the agreed 6–8 envelope.

### Grounded findings (what's actually duplicated vs. by-design)

| Suspected duplication | Ground truth | Verdict |
|---|---|---|
| Two memory systems (xnch L0–L3 vs agentmemory :3111) | Real overlap in recall paths; `memory-routing.yaml` split already exists informally | Consolidate roles, make routing authoritative |
| 4 runner/agent dirs | `agent-runner` (Mac worker) and `cli` (human CLI) are *clients*, not duplicates. `exec_agent/` + `fs_read_agent/` are near-ident twins importing `xnch_mcp` backends | Merge the 2 sidecars; group the 2 clients |
| Policy in 3 places | nexi `PolicyFilter` already delegates to xnch engine (`check_policies_parallel`). `policies/` dirs are per-service config data. `security/` is guards, not policy | No code moves — clarify single-homes in docs |
| Execution split across services | `xnch/agents/` (orchestration, HITL, pipeline_runtime) vs `nexi/pipeline|execution|workflow|goal|proactivity/` — boundary undocumented, some overlap suspected (`xnch/jobs/goal_dispatch.py`, `workflow_schedule.py`) | Audit + document boundary; move only confirmed duplicates |

---

## 2. Current State Inventory

### 2.1 Code

| Package | ~LOC (non-test) | Role |
|---|---|---|
| `xnch/` (submodule) | 14,142 | Control plane: memory (20+ modules), policy, security, auth, perception, audit, learning, routing, jobs, voice, agents, skills, routes |
| `nexi/` (submodule) | 6,811 | Decision engine: 12-step pipeline, persona/character, goal, proactivity, workflow, adapters, execution |
| `xnch_mcp/` | 4,320 | MCP server + federated bridge, exec/fs capability layers, scraper handlers |
| `cli/` | 1,601 | Human CLI (typer): chat, voice, memory queries |
| `scraper/` | 1,476 | 3-tier crawler + RAG ingest (wired into xnch lifespan) |
| `fs_read_agent/` | 194 | Read-only fs sidecar (node-b), imports `xnch_mcp.fs.local.LocalFsBackend` |
| `exec_agent/` | 84 | Governed exec sidecar (node-b), imports `xnch_mcp.exec.local.LocalExecBackend` |

### 2.2 Runtime (app-level services)

| Service | Node | Port | Unit |
|---|---|---|---|
| xnch gateway | A (192.168.50.1) | :8001 | `node-a/systemd/xnch.service` |
| nexi | B (192.168.50.2) | :8000 | `node-b/systemd/nexi.service` |
| exec-agent sidecar | B | (exec port) | `node-b/systemd/exec-agent.service` |
| fs-read-agent sidecar | B | (fs port) | `node-b/systemd/fs-read-agent.service` |
| agentmemory | — | :3111 | external, `am_*` tools, `AGENTMEMORY_SECRET` |
| web (Next.js muse UI) | A | — | compose |
| perception | A | — | `node-a/systemd/perception.service` (extraction precedent) |
| vLLM Ornith-1.0-35B / LiteLLM | B | :8082 / :4000 | infra |
| consolidation cron | A | — | `consolidation.timer` (6h) |
| agent-runner | Mac | — | launchd `com.xnch.agent-runner` |

### 2.3 Key wiring facts

- `xnch/main.py` lifespan constructs stores directly: `PgEpisodicStore`, `ScraperDocumentStore(s.pg_episodic._pool)` (scraper shares the episodic pool), `GraphStore` (Kuzu), plus `PatternExtractor`, `WeightEvolver`, `PolicyRuleEvolver`.
- `nexi/pipeline/policy_filter.py` calls `self._xnch.check_policies_parallel(...)` — policy evaluation is already centralized in xnch at runtime.
- `infra/no-k3s/shared/memory-routing.yaml` (example) already declares: `primary: xnch_episodic`, `curated: agentmemory`, with per-intent routing rules and `deprecate_store_note_for: [nexi]`.
- `xnch/memory/routing_policy.py` + `agentmemory_prefetch.py` already bridge the two memory systems.
- `xnch_mcp/exec|fs/` each contain `local.py` + `remote_client.py` + `service.py` — three transport modes for two capabilities, plus two separate sidecar apps at repo root.

---

## 3. Goals, Non-Goals, Success Criteria

### Goals
1. **One home per domain** — memory, policy, execution each live in exactly one place (code + docs).
2. **Independent deployability** for extracted services (separate systemd units, restart isolation, independent upgrade).
3. Stable external contracts throughout.

### Non-Goals
- No k8s return; systemd + docker-compose only.
- No policy-service / audit-service extraction (per-decision latency-bound; extraction buys only network hops).
- No rewrite of nexi pipeline or xnch routes.
- No changes to `am_*` / `xnch_*` tool signatures.

### Success Criteria
- Touching exec/fs capability = editing one sidecar + one `xnch_mcp` layer (not 4 places).
- Memory consolidation cron restart does not restart the xnch gateway (and vice versa).
- All existing tests green; no MCP tool signature changes; web UI + chat + runner dispatch behaviorally unchanged.
- Service count ≤ 8 app-level deployables.

### Constraints
- 2 nodes: A (i7, memory-bound), B (i9, inference).
- External contracts frozen (see Goals #3).
- Cross-submodule absolute imports forbidden (AGENTS.md) — use adapter/client pattern.

---

## 4. Target Architecture

```
                        ┌───────────────────────── Node A (192.168.50.1, i7) ─────────────────────────┐
                        │                                                                             │
  web UI (muse) ──────►│  xnch gateway :8001          memory-service :8003  ◄── NEW (Phase 2)       │
  cli (human) ────────►│   ├─ routes/auth/audit        ├─ L0 SensoryBuffer (Redis)                    │
  agent-runner (Mac) ─►│   ├─ policy engine            ├─ L1 WorkingMemory (Redis)                    │
                        │   ├─ security guards          ├─ L2 PgEpisodicStore + pgvector               │
                        │   ├─ learning (Pattern→ …)   ├─ L3 GraphStore (Kuzu) + relationships         │
                        │   └─ MemoryClient ───────────► ├─ embeddings (ONNX MiniLM 384d)            │
                        │        (adapter)               ├─ scraper_documents store                     │
                        │                                └─ consolidation cron (6h)                    │
                        │  perception.service (existing unit, untouched)                            │
                        └─────────────────────────────────────────────────────────────────────────────┘
                        ┌───────────────────────── Node B (192.168.50.2, i9) ─────────────────────────┐
                        │  nexi :8000 (12-step pipeline)                                         │
                        │  capability sidecar :8090  ◄── MERGED (Phase 1: exec + fs routers)       │
                        │  vLLM :8082 / LiteLLM :4000                                           │
                        └────────────────────────────────────────────────────────────────────────────┘
  agentmemory :3111 (existing external service, am_* MCP tools) — role: curated cross-session knowledge
```

### Service count after both phases
gateway, memory-service, nexi, capability sidecar, perception, agentmemory, web = **7 app-level** (+ vllm/litellm/redis/postgres infra). Within envelope.

---

## 5. Component Specs

### 5.1 Capability Sidecar (Phase 1) — merge `exec_agent/` + `fs_read_agent/`

**What:** One FastAPI app, `capability_agent/` (new top-level dir), mounting two routers: `exec` and `fs`.
**Keeps:**
- All endpoints, request/response models, and policy files unchanged (`infra/no-k3s/shared/exec-policy.yaml`, `fs-policy.yaml`).
- Fail-closed token auth (`X-Internal-Token`); one shared token setting `XNCH_CAPABILITY_TOKEN` (supersedes `exec_agent_token` / `fs_agent_token`; keep old settings as aliases during migration).
- Backends still come from `xnch_mcp.exec.local.LocalExecBackend` / `xnch_mcp.fs.local.LocalFsBackend` — no logic duplication.
**Changes:**
- Single process, single port (`:8090`, confirm free on node-b), single systemd unit `xnch-capability.service` replacing both `exec-agent.service` and `fs-read-agent.service`.
- `xnch_mcp/exec/remote_client.py` + `xnch_mcp/fs/remote_client.py` retargeted to the merged base URL (internal contract, updated atomically with deploy).
- `service.py` in `xnch_mcp/exec|fs/` collapsed into one shared transport module (see 5.2).
**Migration:** run merged sidecar alongside old ones (different ports) → flip `remote_client` base URLs → verify → stop old units → delete `exec_agent/`, `fs_read_agent/` dirs.

### 5.2 xnch_mcp exec/fs layer retarget (Phase 1)

**Problem:** the two root sidecars (`exec_agent/`, `fs_read_agent/`) each duplicate policy-path resolution, token verification, and backend wiring — and there are two `xnch_mcp` HTTP clients targeting them on two ports.
**Spec:**
- The sidecar app lives once in the new `capability_agent/` package (see 5.1); root sidecar dirs are deleted after cutover.
- `xnch_mcp` keeps: `local.py` backends (used for same-node/dev), `policy.py` loaders, per-capability typed `remote_client.py` files — retargeted to the merged sidecar's `/exec/*`, `/fs/*` paths via a capability-first, legacy-fallback settings chain (`XNCH_CAPABILITY_NODE_B_URL` wins; `exec_agent_node_b_url`/`fs_agent_node_b_url` remain as rollback).
- `service.py` dispatchers (local-vs-remote routing) are NOT sidecars and stay as-is apart from the settings chain change.

### 5.3 Policy single-home (Phase 1 — docs + guards, no code moves)

**Spec:**
- `xnch/policy/` = the ONLY policy evaluation engine (loader, engine, validator, audit_logger).
- `xnch/policies/default.yaml` + `nexi/policies/default.yaml` = per-service policy *data* (by design; each service loads its own YAML).
- `nexi/pipeline/policy_filter.py` = the only policy call path from nexi (already delegates via `check_policies_parallel` — no change).
- `xnch/security/` = guards (trust tiers, injection/memory guards, sandbox, gateway tokens) — a different concern; never to be merged into `xnch/policy`.
- Deliverable: "Single-Home Registry" section in AGENTS.md (table: domain → the one package → what everything else must do to use it).

### 5.4 Memory role split (Phase 1 — formalize what exists)

**Spec (makes `memory-routing.yaml` authoritative):**
- **xnch memory (L0–L3)** = runtime, episodic, high-volume memory of the living system. Recall path for conversations, decisions, episodic context.
- **agentmemory (:3111)** = curated cross-session knowledge (facts, lessons, work items, deploy lessons). Reached ONLY via `am_*` MCP tools.
- Routing table is the single decision point (`primary: xnch_episodic`, `curated: agentmemory`); `xnch/memory/routing_policy.py` enforces it; `deprecate_store_note_for: [nexi]` becomes a hard rule — `xnch_memory_store_note` from actor `nexi` returns a deprecation error pointing at `am_*`.
- One-way bridge only: runtime episodic → curated (existing `agentmemory_prefetch.py`), never reverse. No parallel recall paths.

### 5.5 Clients grouping (Phase 1 — cosmetic but clarifying)

- New top-level `clients/`: move `cli/` → `clients/cli/`, `agent-runner/` → `clients/agent-runner/`.
- Update `com.xnch.agent-runner.plist` template paths, README instructions, and any scripts referencing old paths.
- These are *clients of the system*, never servers — the grouping makes the top level read: control plane (`xnch`), engine (`nexi`), MCP surface (`xnch_mcp`), capabilities (`capability_agent`), data services (`scraper`, memory-service later), clients, infra.

### 5.6 Execution boundary audit (Phase 1 — bounded investigation with deliverable)

- Audit `xnch/agents/` (decision_state, hitl, pipeline_graph, pipeline_runtime) + `xnch/jobs/` (goal_dispatch, workflow_schedule) vs `nexi/pipeline|execution|workflow|goal|proactivity`.
- Deliverable: boundary doc in `docs/architecture/execution-boundary.md` defining: nexi = *deciding & running the 12-step pipeline*; xnch = *orchestrating agent runs, HITL approvals, scheduling crons that call nexi*.
- Move code ONLY where a confirmed duplicate exists (candidate: `xnch/jobs/workflow_schedule.py` if it duplicates `nexi/workflow/executor.py` scheduling); otherwise document and leave.

### 5.7 Memory-service extraction (Phase 2)

**Deployment shape (recommended — option b):**
- New entrypoint INSIDE the xnch submodule: `python -m xnch.memory.server` — a FastAPI app exposing the stores over internal HTTP. No code moves across submodule boundaries (respects AGENTS.md import rules, keeps all existing `xnch/tests` valid).
- Trade-off acknowledged: repo-level releases stay coupled to the xnch submodule, but *deploy* is independent (own systemd unit, own restart, own resource envelope). Full code separation (option a: new top-level package) is a possible later step once the HTTP boundary proves itself.

**API surface (internal, gateway-only, token-auth like the capability sidecar):**
- `POST /v1/call` — generic dispatch `{"store": "pg_episodic"|"graph_store"|"relationship_store"|"working_memory"|"sensory_buffer"|"scraped_store", "method": str, "args": [...], "kwargs": {...}}`, guarded by a strict `(store, method)` whitelist (reviewed against the verified consumer surface). One endpoint keeps the client/proxy tiny and the whitelist explicit; adding a method = one whitelist tuple + one test.
- `GET /healthz` — checks Postgres (pool `SELECT 1`) and Kuzu (`get_stats()`), reports `{"status": "ok"|"degraded", "tiers": {...}}`
- `POST /v1/consolidation/run` — invokes the consolidation pipeline (6h timer targets this)
- `GET /v1/graph/stream` — SSE stream of graph mutations (the gateway's `/graph/stream` relays it in remote mode)

**Gateway change:**
- `xnch/main.py` lifespan swaps direct store construction for `MemoryClient` (adapter class, same interface as the stores it replaces — mirror the existing `XnchClient` adapter pattern used by nexi).
- **Rollback switch:** `XNCH_MEMORY_EMBEDDED=1` (default during migration) runs stores in-process exactly as today. This is the phase-2 rollback path and the migration bridge.

**Node placement:** Node A (memory-bound i7) beside Postgres/Kuzu data dirs. Port `:8003` (confirm free).

**What moves behind the service:** `xnch/memory/` store construction, scraper document store, consolidation cron trigger, embeddings (ONNX MiniLM) for recall-side embedding needs.
**What stays in gateway:** route handlers, auth, policy engine, learning orchestration (PatternExtractor etc. keep running against memory-service via client).

---

## 6. Data Flow (after both phases)

```
User → web/cli → xnch gateway :8001
  ├─ conversation recall ──► MemoryClient ──► memory-service :8003 ──► Redis/Postgres/Kuzu
  ├─ decision: policy dry-run (in-gateway xnch/policy engine)
  └─ dispatch → nexi :8000 (12-step pipeline) ──► policy_filter ──► gateway check_policies_parallel
                                    └─ execute tool → xnch_mcp bridge
                                         ├─ exec/fs tools ──► capability sidecar :8090 (node-b)
                                         └─ am_* tools ──► agentmemory :3111 (curated only)
Learning cron (6h) → memory-service /v1/consolidation/run → L2→L3 consolidation
Scraper MCP tools → xnch_mcp/handlers/scraper.py → memory-service /v1/scraper/*
agent-runner (Mac) → gateway dispatch queue (unchanged contract)
```

## 7. Error Handling

- Capability sidecar + memory-service: fail-closed token auth (unconfigured token = loud 503, never silent open) — matches existing sidecar convention.
- `MemoryClient` in gateway: per-call timeouts (recall ≤ 2s budget, matching current embedded latency + slack), retry x1, then degrade: fall back to L1 WorkingMemory/Redis direct read for reads; queue writes to `sensory_buffer` for replay — recall must never hard-fail a chat turn.
- `XNCH_MEMORY_EMBEDDED=1` emergency rollback (documented in runbook).
- All new services emit to the existing EventLog JSONL + Prometheus scrape targets.

## 8. Testing Strategy

| Layer | What |
|---|---|
| Unit | `capability_agent` router tests (mirror `fs_read_agent/tests` style); `MemoryClient` with `httpx.MockTransport` |
| Contract | MCP tool signatures: golden-file test asserting `xnch_*`/`am_*` tool defs unchanged; sidecar endpoint schemas unchanged vs old apps |
| Integration | `tests/` e2e: chat pipeline 12-step pass with `XNCH_MEMORY_EMBEDDED=0` against a locally-running memory-service (test fixture boots `xnch.memory.server` on ephemeral port) |
| Migration | Dual-run checks: merged sidecar + old sidecars both serving; `remote_client` flip verified by exec/fs policy tests |
| Ops | `consolidation.timer` fires against memory-service; audit chain (DecisionLedger SHA-256) unbroken across the boundary change |

---

## 9. Task Breakdown

**Legend:** [P]hase, priority (1 high – 3 low), depends-on. Each task lists files + verification. Commit granularity = one task (or sub-task) per commit.

### Phase 0 — Foundations
| ID | Task | Files | Verify |
|---|---|---|---|
| T0.1 | Baseline test run + service inventory snapshot (ports, units, health endpoints) | `misc/` snapshot | `pytest` green; inventory committed |
| T0.2 | Confirm `:8090` free on node-b, `:8003` free on node-a | runbook note | `ss -ltn` on both nodes |

### Phase 1 — Consolidation
| ID | Task | Pri | Depends | Files | Verify |
|---|---|---|---|---|---|
| T1.1 | Create `capability_agent/` app: FastAPI with exec + fs routers, shared token dep, port :8090; port old settings as aliases | new `capability_agent/` | T0.2 | router tests pass; endpoints byte-compatible with old sidecars (diff OpenAPI schemas) |
| T1.2 | Collapse `xnch_mcp/exec|fs` `service.py`+`remote_client.py` into shared `remote.py`; retarget to `XNCH_CAPABILITY_URL` | `xnch_mcp/exec/`, `xnch_mcp/fs/` | T1.1 | `xnch_mcp` tests green |
| T1.3 | Deploy merged sidecar on node-b (both old units still running); flip `remote_client` env; verify; stop old units; add `xnch-capability.service` | `infra/no-k3s/node-b/systemd/` | T1.1, T1.2 | exec/fs MCP tools succeed via new sidecar; old units stopped |
| T1.4 | Delete `exec_agent/`, `fs_read_agent/`; update docs | root dirs | T1.3 | `pytest` + grep for stale imports |
| T1.5 | Promote memory-routing to authoritative: enforce `deprecate_store_note_for` hard rule for actor `nexi` | `xnch/memory/routing_policy.py`, `infra/no-k3s/shared/memory-routing.yaml` | — | test: nexi `store_note` → deprecation error naming `am_*` |
| T1.6 | Single-Home Registry in AGENTS.md (policy, security, memory roles, execution boundary pointer) | `AGENTS.md` | T1.5 | review |
| T1.7 | Execution boundary audit + `docs/architecture/execution-boundary.md`; move confirmed duplicates only (candidate: `xnch/jobs/workflow_schedule.py` vs `nexi/workflow/executor.py`) | docs + audited code | — | boundary doc approved; moved code covered by existing tests |
| T1.8 | Group clients: `clients/cli/`, `clients/agent-runner/`; fix plist template + README paths | moves, `com.xnch.agent-runner.plist` | — | `python -m clients.cli` works; plist paths updated |

### Phase 2 — Memory-service extraction
| ID | Task | Pri | Depends | Files | Verify |
|---|---|---|---|---|---|
| T2.1 | `xnch/memory/server.py` FastAPI app: store endpoints (§5.7 surface), fail-closed token, `/healthz` | `xnch/memory/` (submodule) | T0.2 | new unit tests; OpenAPI spec committed |
| T2.2 | `MemoryClient` adapter in gateway with identical interface to embedded stores; `XNCH_MEMORY_EMBEDDED` switch (default `1`) | `xnch/main.py`, new `xnch/memory_client.py` | T2.1 | gateway tests pass in both modes |
| T2.3 | Retire direct store construction in lifespan behind the client (incl. `ScraperDocumentStore`, PatternExtractor/evolvers wiring) | `xnch/main.py` | T2.2 | `pytest xnch/tests` green both modes |
| T2.4 | Degrade path: recall fallback to Redis L1 + write replay via sensory buffer | `xnch/memory_client.py` | T2.2 | fault-injection test (kill memory-service mid-test) |
| T2.5 | Deploy `xnch-memory.service` on node-a :8003; flip `XNCH_MEMORY_EMBEDDED=0`; re-target `consolidation.timer`; add Prometheus scrape | `infra/no-k3s/node-a/systemd/` | T2.3, T2.4 | e2e chat pass; consolidation fires; gateway restart-free memory restart |
| T2.6 | Runbook: rollback via `XNCH_MEMORY_EMBEDDED=1`; ops doc for new units | `docs/runbooks/` | T2.5 | review |

### Phase 3 — Verification & hardening
| ID | Task | Depends | Verify |
|---|---|---|---|
| T3.1 | Golden-file contract test for all MCP tool defs (`xnch_*`, `am_*` passthroughs) | T1.x, T2.x | tool defs byte-identical to pre-split snapshot |
| T3.2 | Full e2e: web UI smoke, chat 12-step, runner dispatch, scraper tools, HITL approval | all | `pytest tests/` green |
| T3.3 | Update `README.md`, `docs/architecture-suite.md`, AGENTS.md mental model, onboarding order | all | docs review |
| T3.4 | Observability: dashboards for capability sidecar + memory-service (latency, error rate, consolidation duration) | T2.5 | dashboards render |

### Sequencing summary
```
T0.1,T0.2 → T1.1 → T1.2 → T1.3 → T1.4
         → T1.5 → T1.6
         → T1.7 (independent)
         → T1.8 (independent)
T2.1 → T2.2 → T2.3 → T2.4 → T2.5 → T2.6
T3.1 → T3.2 → T3.3, T3.4 (last)
```
Phase 1 and Phase 2 are separable: Phase 1 alone already delivers 3 of 4 redundancy fixes.

---

## 10. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Recall latency through HTTP boundary hurts chat UX | Medium | keep `kv_cache`; 2s budget; degrade path (T2.4); `XNCH_MEMORY_EMBEDDED` rollback |
| Dual-run window writes to wrong sidecar/store | Low | single flip point per cutover; audit events on both sides during window |
| Losing tests when deleting `exec_agent/`/`fs_read_agent/` | Low | port their tests into `capability_agent/tests` in T1.1, not T1.4 |
| Submodule coupling limits "independent deploy" (option b) | Accepted | documented trade-off; option a (full code move) available post-boundary-proof |
| `clients/` move breaks launchd plist in the field | Low | plist already requires manual install (README documents re-copy) |
| Port collision :8090/:8003 | Low | T0.2 checks first |

## 11. Open Questions (resolve before Phase 2)
1. Should `agentmemory_prefetch` sync move into memory-service, or stay in gateway? (Leaning: gateway — it's a bridge concern, not a store concern.)
2. Does the vault-indexer / perception stack already own port :8003? (T0.2 answers.)
3. Eventually move `xnch/memory` fully out of the submodule (option a)? Deferred until boundary proves stable in prod for one consolidation cycle.
