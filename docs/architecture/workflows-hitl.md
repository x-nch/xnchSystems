# Workflows & HITL Approvals

Audience: devs/operators. Sources: `xnch/routes/workflows.py`,
`xnch/memory/workflow_store.py`, `nexi/workflow/executor.py`,
`web/src/lib/{workflows,approvals}/`,
[workflows backend spec §4](../superpowers/specs/2026-08-22-workflows-backend-design.md)
(immutable design record).

Workflows are multi-step, human-gated action sequences. Each **run** produces
per-**step** records; gated steps surface in a unified **approvals queue**
alongside other producers (e.g. verdict proposals). muse renders both
([operate HITL guide](../guides/operate-hitl.md)).

## State machines

Step: `PENDING → AWAITING_APPROVAL → APPROVED → CLAIMED → DONE`
with side states `RETRYING → FAILED`, plus terminal `REJECTED | EXPIRED |
CANCELLED`.

Run: `RUNNING → COMPLETED | FAILED` (any hard-failed step fails the run).

Approval semantics depend on the executor flag:

| `XNCH_WORKFLOW_EXECUTOR_ENABLED` | approve ⇒ |
|---|---|
| `false` (v1 default) | step **DONE** immediately (no executor deployed) |
| `true` (P2) | step **APPROVED**, left for nexi's executor to claim |

Reject ⇒ approval `REJECTED` and the produced step cancelled.

## Executor claim-lease semantics (`nexi/workflow/executor.py`)

Serialized loop, survives transient errors:

1. `POST /workflows/steps/claim` `{lease_owner: "nexi-wf-executor",
   ttl_s}` (default TTL 120 s; server-side knob
   `XNCH_WORKFLOW_STEP_CLAIM_LEASE_S`). The claim is an atomic SQL update:
   takes an `APPROVED` step, or a due `RETRYING` step, or a stale `CLAIMED`
   whose `lease_expires_at` has passed. No work → `204`.
2. Execute the claimed step through one pipeline pass.
3. Report `POST /workflows/steps/{uuid}/outcome`. The API accepts
   `SUCCESS | PARTIAL | FAILURE`, but the nexi executor emits only
   `SUCCESS` or `FAILURE` today.
   - `SUCCESS/PARTIAL` ⇒ step `DONE`.
   - `FAILURE` ⇒ `RETRYING` with backoff until `max_retries`, then `FAILED`.
4. Lease release is **implicit by expiry** — there is no explicit release
   call; a crashed executor's steps become reclaimable once the lease lapses.

Enabled on nexi via `NEXI_WORKFLOW_EXECUTOR_ENABLED=true`
(poll interval `NEXI_WORKFLOW_POLL_INTERVAL_S`=5).

## Hybrid-B write gate

All state-changing endpoints below require gateway access: a short-lived HMAC
token (`X-Gateway-Token: <expiry>.<hmac_sha256(secret, expiry)>`, minted by the
muse proxy from `XNCH_GATEWAY_SECRET`) **or** the shared service key presented
by nexi. Empty secret = gate open (dev/test only). Details + header matrix:
[auth model](../reference/auth-model.md).

## API surface

| Endpoint | Gate | Purpose |
|---|---|---|
| `POST /workflows` (201) | gateway | create workflow definition |
| `GET /workflows` · `GET /workflows/{id}` | open | list / inspect |
| `PATCH /workflows/{id}` · `DELETE /workflows/{id}` (204) | gateway | modify / delete |
| `POST /workflows/{id}/run` (201) | gateway | start a run |
| `GET /workflows/runs` | open | run history |
| `POST /workflows/steps/claim` | gateway (service) | executor lease claim |
| `POST /workflows/steps/{uuid}/outcome` | gateway (service) | SUCCESS/PARTIAL/FAILURE |
| `GET /approvals?status=&producer_type=&limit=` | open | unified queue |
| `GET /approvals/{id}` | open | single approval |
| `POST /approvals/{id}/decide` | gateway | approve/reject (+`Idempotency-Key` header) |

Request/response schemas are Pydantic models in
`xnch/routes/workflows.py`; curl walkthroughs:
[build a workflow](../guides/build-workflow.md).
