# Workflows Backend — Design Spec
### HITL-gated playbooks for xnchSystems (xnch control plane + nexi executor)

**Date:** 2026-08-22
**Status:** Approved direction (post external review v2)
**Constraint:** No commits / no deploys this pass. Implementation + e2e tests only.
**Related:** `docs/superpowers/specs/2026-08-22-xnchsystems-hitl-dark-minimalist-design.md` (UI queue spec), UI prototype at `web/src/components/workflows/workflows-view.tsx`

---

## 0. Problem

Backend has **no workflows** (0 doc hits across `docs/architecture-suite.md`, `docs/reference/`) and **no HITL approvals store** — the operator approval queue (`/` route) is currently UI-local Zustand/localStorage. This spec adds durable workflows to xnch and a first-class approvals table that any producer (chat, tool_call, goal_step, workflow_step) can write to.

## 1. Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Approvals model | **First-class generic `approvals` table** day one | Multiple producers incoming; avoids rewrite under load |
| Workflow→Goals coupling | **None** — copy lease pattern, don't inherit Goals | Goals unverified/unimplemented; step ≠ goal semantics |
| Steps storage v1 | **JSON array on `workflow_runs.steps_json`** | v1 has no executor; row-level atomic claims only matter Phase 2 |
| Expiry | **Lazy on read** (`GET /approvals`, claim queries) | No second cron; 6h consolidate too coarse for 1h TTL |
| Scheduler | Phase 3 lifespan asyncio task w/ **restart catch-up scan** | Single-node; restart must re-scan `next_due_at <= now` |
| Auth (new endpoints) | **Hybrid-B**: proxy mints short-lived HMAC token; xnch requires it on `/workflows/*` + `/approvals/*` only | Protects highest-blast-radius writes day one; zero change to existing chat/tools auth |
| nexi credential | Scoped service identity locked to `claim` + `outcome` endpoints (Phase 2) | Service ≠ operator token |
| Commits | Per-submodule (`xnch`←P1+P3, `nexi`←P2); root gets docs only | Monorepo convention — **suspended this pass per user** |
| Timestamps | UTC-pinned epoch seconds (`time.time()`), matching GoalStore convention | Avoids clock-drift expiry bugs |

## 2. Schema

```sql
-- workflows: durable definitions
CREATE TABLE IF NOT EXISTS workflows (
  id TEXT PRIMARY KEY,
  owner_actor_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  trigger_json TEXT NOT NULL DEFAULT '{}',   -- {"kind":"manual"} | {"kind":"schedule","cron":"0 9 * * 1"}
  steps_json TEXT NOT NULL DEFAULT '[]',     -- definition template (WorkflowStep[])
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

-- workflow_runs: execution instances; steps embedded v1
CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL REFERENCES workflows(id),
  status TEXT NOT NULL CHECK (status IN ('RUNNING','COMPLETED','FAILED','CANCELLED')),
  trigger_json TEXT NOT NULL DEFAULT '{}',
  steps_json TEXT NOT NULL DEFAULT '[]',     -- RunStep[] (has runtime state; see §3)
  idempotency_key TEXT UNIQUE,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status);

-- approvals: FIRST-CLASS, producer-agnostic
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  producer_type TEXT NOT NULL CHECK (producer_type IN ('chat','tool_call','goal_step','workflow_step')),
  producer_id TEXT NOT NULL,                 -- run step uuid for workflow_step
  payload_json TEXT NOT NULL,                -- action summary/target/args/preview
  status TEXT NOT NULL CHECK (status IN ('AWAITING_APPROVAL','APPROVED','REJECTED','EXPIRED','CANCELLED')),
  risk_class TEXT NOT NULL DEFAULT 'low',    -- low | elevated (send_email/exec) — gates decide role
  decision_note TEXT,
  decided_by TEXT,
  decided_at REAL,
  expires_at REAL,
  idempotency_key TEXT UNIQUE,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_status_exp ON approvals(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_approvals_producer ON approvals(producer_type, created_at);

-- step_events: APPEND-ONLY audit trail (never UPDATEd)
CREATE TABLE IF NOT EXISTS step_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  step_uuid TEXT NOT NULL,
  event_type TEXT NOT NULL,                  -- RUN_CREATED|APPROVED|REJECTED|EXPIRED|EXECUTING|DONE|FAILED|CANCELLED|ARG_DIFF
  actor TEXT NOT NULL,
  ts REAL NOT NULL,
  snapshot_json TEXT NOT NULL                -- full step/approval snapshot at event time
);
CREATE INDEX IF NOT EXISTS idx_events_step ON step_events(step_uuid);
```

## 3. State machines

**RunStep** (inside `steps_json`; promoted to rows in Phase 2):
```
PENDING → AWAITING_APPROVAL (requires_approval=true; approval row created at run time)
        → EXECUTING_DONE    (requires_approval=false, v1 auto-done)
AWAITING_APPROVAL → APPROVED (v1 terminal = DONE) | REJECTED | EXPIRED | CANCELLED
```
v1 has no executor: `APPROVED` ⇒ step `DONE`, run advances; all steps resolved ⇒ run `COMPLETED`.

**Approval row**: `AWAITING_APPROVAL → APPROVED | REJECTED | EXPIRED | CANCELLED`. Terminal states immutable — `decide()` returns 409 unless status is `AWAITING_APPROVAL`. Lazy expiry flips past-due rows inline on read.

## 4. API surface (mounted under existing auth)

| Method/Path | Role | Notes |
|---|---|---|
| `POST /workflows` | operator+ | body `{name, description?, trigger{kind,cron?}, steps[]}`, optional `Idempotency-Key` header |
| `GET /workflows` · `GET /workflows/{id}` | viewer+ | list/get |
| `PATCH /workflows/{id}` · `DELETE /workflows/{id}` | operator+ | owner or admin for delete |
| `POST /workflows/{id}/duplicate` | operator+ | |
| `POST /workflows/{id}/run` | operator+ | creates run + approval rows per gated step; honors `Idempotency-Key` |
| `GET /workflows/runs?status=&workflow_id=` | viewer+ | recent runs |
| `GET /approvals?status=pending&producer_type=` | viewer+ | lazy-expires past-due first |
| `POST /approvals/{id}/decide` | operator+ (**elevated risk_class ⇒ admin**) | `{decision:"approve"|"reject", note?}`; 409 if not awaiting; honors `Idempotency-Key` |

**Auth gate (Hybrid-B):** dependency `require_gateway_token` on all `/workflows/*`(writes)+`/approvals/*`: accepts either (a) valid HMAC `X-Gateway-Token` (short-lived, minted by web proxy, shared secret `XNCH_GATEWAY_SECRET`) or (b) internal service credential (nexi, Phase 2). Legacy routes untouched. Verify against real auth middleware during Phase 0 discovery; if xnch already enforces CF-Access/actor headers globally, layer rather than duplicate.

## 5. Phases

- **P0 Discovery** — submodule init; confirm: db.py location/migration style, auth middleware reality, Goals implemented?, pipeline entrypoint for P2.
- **P1 xnch core** — models → schema/store (TDD) → routes → wire → pytest green. Manual runs only; approve⇒DONE.
- **P2 nexi executor** — promote RunSteps to own table w/ atomic claims; executor loop calls pipeline; outcome callback. *(follow-up)*
- **P3 scheduler** — lifespan task, restart catch-up scan. *(follow-up)*
- **P4 web swap** — React Query via `/api/gateway/*`; Zustand→cache-only. *(follow-up)*

**This pass scope:** spec + P0 + P1 + e2e tests. No git commits, no deploys.

## 6. Verification

- `pytest xnch/tests/test_workflow_store.py xnch/tests/test_workflow_routes.py xnch/tests/test_approvals.py -v`
- E2E: FastAPI TestClient — create wf → run → approvals appear pending → decide approve → run COMPLETED → step_events trail complete → decide-again 409 → expiry flip on read.
