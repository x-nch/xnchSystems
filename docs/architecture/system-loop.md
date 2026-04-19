# System Loop

---
tags:
  - #architecture
  - #execution
  - #memory
  - #learning
---

How xnch + Nexi operates end-to-end, continuously, over time.

This document describes the complete operational loop — from raw input through execution and back into the system as structured memory. It does not describe the internals of any single component. For those, see [[_system-map.md]]:

## Related

- [[_system-map.md]]
- [[_decision-map.md]]
- [[_memory-map.md]]

---

## Event Log — Cross-Cutting Layer

The Event Log is not a step in the loop. It is active across every step boundary.

Every state transition — from input ingestion through memory write-back — emits a structured event to the Event Log (`~/.xnch/audit/events.jsonl`) via the audit-logger process. This is fire-and-forget (UDP) from each component and does not block the main request path. The Decision Ledger write at Step 11 is the only synchronous audit operation.

Each event carries `trace_id`, `component`, `event_type`, and `timestamp_ns`. The `trace_id` assigned at Step 1 is the thread that makes the full Event Log sequence for a session reconstructible. See [`components/audit.md — Event Log`](../components/audit.md#event-log) for the event schema and component event types.

```
Step 1 ──emit──▶ ┐
Step 2 ──emit──▶ │
Step 2a ─emit──▶ │   Event Log  (async, append-only, UDP)
Step 3 ──emit──▶ │   events.jsonl
Step 4 ──emit──▶ │
Step 5 ──emit──▶ │   All events carry trace_id.
Step 6 ──emit──▶ │   No step is silent.
Step 7 ──emit──▶ │
Step 8 ──emit──▶ │
Step 9 ──emit──▶ │
Step 10 ─emit──▶ │   + Decision Ledger write (SYNC, inside xnch)
Step 10a ─emit─▶ │
Step 11 ─emit──▶ │
Step 12 ─emit──▶ │
Step 13 ─emit──▶ │
Step 14 ─emit──▶ │
Step 15 ─emit──▶ ┘
```

---

## Loop Diagram

```
                    ┌─────────────────────────────────┐
                    │          ACTOR                  │
                    │   (Human / Agent / System)      │
                    └──────────────┬──────────────────┘
                                   │ Raw Input
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                        INGESTION                                  │
│  [1]  Input Layer — transport validation, trace_id, idempotency  │
│                         │                                        │
│  [2a] xnch → KV Cache — session lookup, rate limit check        │
│                         │                                        │
│  [2]  xnch — auth verify, actor→role resolve, state version pin  │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Session Context
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      INTENT + CONTEXT                            │
│  [3] Nexi — Intent Normalization                                 │
│             ambiguity_score > 0.7 → CLARIFICATION_REQUIRED ─────┐│
│                         │                                        ││
│  [4] xnch → Nexi — Context Manifest (episodes, patterns,        ││
│             policies) pinned at system_state_version             ││
└──────────────────────────────┬───────────────────────────────────┘
                               │ Intent + Manifest
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                     OPTION GENERATION                            │
│  [5] Nexi → Model Adapter → vLLM                                 │
│             Constrained prompt, N=5 structured options           │
│             Model failure → rule-based fallback (DEGRADED)      │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Plan Options (raw)
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                     POLICY FILTER                                │
│  [6] Nexi → xnch — Parallel policy dry-run per option           │
│             BLOCK → drop   MODIFY → rewrite spec                 │
│             All BLOCK → ESCALATE ────────────────────────────────┐│
└──────────────────────────────┬───────────────────────────────────┘
                               │ Policy-clean options
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      EVALUATION                                  │
│  [7] Nexi — Score 4 dimensions per option                        │
│             policy_score · outcome_score · risk · context_fit    │
│                                                                  │
│  [8] Nexi — Outcome Simulation (conditional)                     │
│             Risk > 0.6 | irreversible | agent actor              │
│             All simulate to violation → ESCALATE ────────────────┐│
└──────────────────────────────┬───────────────────────────────────┘
                               │ Evaluated + simulated options
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      SELECTION + VERDICT                         │
│  [9]  Nexi — Select highest composite, assemble Decision Record  │
│                                                                  │
│  [10a] Plan Compiler — validate action_spec (structure + params) │
│                                                                  │
│  [10] xnch — Final authoritative policy check                    │
│              State version match, Decision Ledger write (sync)   │
│              BLOCK → ESCALATE · ALLOW → execution_token issued   │
└──────────────────────────────┬───────────────────────────────────┘
                               │ execution_token + validated action_spec
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       EXECUTION                                  │
│  [11] execution-runner — Token validated independently           │
│                          action_spec executed sequentially       │
│  [12] Nexi → Actor — Intermediate: status EXECUTING              │
│  [13] execution-runner → xnch — Outcome posted async            │
└──────────────────────────────┬───────────────────────────────────┘
                               │ ExecutionOutcome
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      MEMORY UPDATE                               │
│  [14] xnch → memory — Episode completed (outcome, delta)         │
│       Nexi — prediction_delta > 0.3 → early extraction flag     │
│  [15] Actor — Final status delivered                             │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Completed episode in store
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      LEARNING (ASYNC)                            │
│  Pattern Extractor (6h or early) — episodes → patterns          │
│  Score Adapter — dimension accuracy < 0.6 → weight proposal     │
│  Policy Candidate Gen — low success patterns → operator review   │
└──────────────────────────────┬───────────────────────────────────┘
                               │ Updated patterns + weights
                               ▼
                    ┌──────────────────────┐
                    │   NEXT ITERATION     │
                    │  outcome_score reads │
                    │  updated patterns    │
                    └──────────────────────┘
```

---

## Step-by-Step Loop

### Step 1 — Input Ingestion

**Component:** Input Layer (CLI / FastAPI gateway)
**Input:** Raw string or structured event from actor
**Output:** Request forwarded to xnch with `trace_id` and `idempotency_key` assigned
**Transformation:** Transport-level validation only — auth token presence, payload size, content-type. No semantic processing. → [`execution-flow.md — Step 1`](execution-flow.md#step-1--input-layer-receives-raw-input-sync)

---

### Step 2a — KV Cache Check (First Memory Interaction)

**Component:** xnch-server → Redis (KV Cache)
**Input:** `actor_id` + source IP (extracted from auth token before verification)
**Output:** Rate limit verdict (pass / reject) + existing session lookup result
**Transformation:** Before any governance store query, xnch checks two things in Redis:

1. **Session lookup** — if the `idempotency_key` matches an active session already in the KV Cache, xnch returns the cached Session Context immediately without repeating actor resolution or state pinning. This deduplicate resubmissions within the session TTL window.
2. **Rate limit** — increments the per-actor request counter for the current window. If the counter exceeds the configured limit, xnch rejects with `429` before touching the governance store. This is the system's first line of defence against request floods.

If both checks pass, the request proceeds to Step 2. The KV Cache is the first and only memory component touched before auth verification. See [`components/xnch.md — Configuration`](../components/xnch.md#configuration) for TTL and rate limit settings.

---

### Step 2 — Session Initialization

**Component:** xnch-server → governance store
**Input:** Raw request + auth token
**Output:** [`xnch Session Context`](../reference/data-contracts.md#xnch-session-context) — actor, role, capability_set, system_state_version, policy_version
**Transformation:** JWT verification, actor→role resolution from governance store, `system_state_version` + `policy_version` pinned. Session Context written to KV Cache with TTL. → [`execution-flow.md — Step 2`](execution-flow.md#step-2--xnch-session-initialization--actor-resolution-sync)

---

### Step 3 — Intent Normalization

**Component:** Nexi — Intent Interpreter
**Input:** Raw input string + Session Context
**Output:** [`Intent`](../reference/data-contracts.md#intent)
**Transformation:** Classification, entity identification, `ambiguity_score` computation. `ambiguity_score > 0.7` → `CLARIFICATION_REQUIRED`, loop paused. → [`execution-flow.md — Step 3`](execution-flow.md#step-3--nexi-intent-interpretation-sync) · [`decision-model.md — Failure and Uncertainty Handling`](decision-model.md#failure-and-uncertainty-handling)

---

### Step 4 — Context Loading

**Component:** xnch-server + memory-store (parallel queries)
**Input:** Intent + actor capability scope
**Output:** [`Context Manifest`](../reference/data-contracts.md#context-manifest) — episodes, patterns, active policies, system_state_version
**Transformation:** Read policy applied per actor capability. Three stores queried in parallel. Manifest pinned and immutable for session lifetime. → [`execution-flow.md — Step 4`](execution-flow.md#step-4--nexi--xnch-context-manifest-request-sync)

---

### Step 5 — Option Generation

**Component:** Nexi — Option Generator → Model Adapter → vLLM
**Input:** Intent + Context Manifest (summary subset)
**Output:** N × [`Plan Option`](../reference/data-contracts.md#plan-option) (raw, schema-validated)
**Transformation:** Model Adapter routes the constrained generation request to the available inference backend. Model output schema-validated; fallback to rule-based generator on failure. → [`execution-flow.md — Step 5`](execution-flow.md#step-5--nexi--model-layer-constrained-generation-request-sync) · [`runtime.md — Model Runtime Paths`](runtime.md#model-runtime-paths)

The Model Adapter is the abstraction layer between Nexi and any inference backend (vLLM, llama-cpp-python, or rule-based fallback). Nexi does not call vLLM directly. See [`components/model-adapter.md`](../components/model-adapter.md).

---

### Step 6 — Policy Alignment Filter

**Component:** Nexi → xnch-server (parallel fanout)
**Input:** N × Plan Option
**Output:** N × [`Policy Dry-Run Response`](../reference/data-contracts.md#policy-dry-run-response)
**Transformation:** Parallel `GET /policy/check` per option. `BLOCK` → dropped. `MODIFY` → spec rewritten. All blocked → `ESCALATED`. → [`execution-flow.md — Step 6`](execution-flow.md#step-6--nexi--xnch-parallel-policy-dry-run-sync-parallel-fanout)

---

### Step 7 — Evaluation

**Component:** Nexi — Option Evaluator
**Input:** Policy-clean Plan Options + Context Manifest
**Output:** N × [`Evaluated Option`](../reference/data-contracts.md#evaluated-option) with per-dimension scores and composite
**Transformation:** Four dimensions scored independently; weighted composite per intent_class weight profile. → [`decision-model.md — Evaluation Criteria`](decision-model.md#evaluation-criteria)

---

### Step 8 — Outcome Simulation (Conditional)

**Component:** Nexi — Outcome Simulator
**Input:** Top 2 Evaluated Options + current system state snapshot
**Output:** Adjusted composite scores
**Transformation:** Forward-projection against current state. Constraint violation → risk re-scored. All options violate → `ESCALATED`. → [`decision-model.md — When Simulation is Triggered`](decision-model.md#when-simulation-is-triggered)

---

### Step 9 — Selection

**Component:** Nexi — Decision Selector
**Input:** Evaluated (and optionally re-scored) options
**Output:** [`Decision Record`](../reference/data-contracts.md#decision-record)
**Transformation:** Highest composite, non-blocked option selected. Full Decision Record assembled with all scores, rationale, `confidence`, `weight_config_version`. → [`execution-flow.md — Step 9`](execution-flow.md#step-9--nexi-decision-selection--record-assembly-sync)

---

### Step 10a — Action Spec Validation

**Component:** Plan Compiler (within nexi-engine process)
**Input:** Selected option's `action_spec` from Decision Record
**Output:** Validated `action_spec` — confirmed structure, required fields present
**Transformation:** The Plan Compiler validates the selected `action_spec` before it proceeds to the final verdict call. It:

1. **Confirms required fields are present** — `type`, `target`, and `params` must all be non-null
2. **Validates field types and values** — `type` must be a known action type; `params` must conform to the schema for that type

The validated `action_spec` is what the execution-runner receives. The runner executes it sequentially. Validation happens after Decision Record assembly (Step 9) and before the final verdict call (Step 10) — the validated `action_spec` is included in the Execution Dispatch Payload issued after the token. If validation fails (missing fields, unknown action type), the session returns an error without reaching Step 10; no execution token is issued and no episode is written.

> **Note:** Multi-step DAG execution (parallel steps, dependency resolution, per-step `retry_config`) is a future enhancement.

---

### Step 10 — Final Verdict

**Component:** xnch-server
**Input:** [`Decision Record`](../reference/data-contracts.md#decision-record)
**Output:** [`Verdict Response`](../reference/data-contracts.md#verdict-response) — execution_token, audit_ref
**Transformation:** Authoritative policy re-evaluation. `system_state_version` match verified. **Decision Ledger write is synchronous here** — the only blocking audit operation in the loop. Execution token issued on `ALLOW`. → [`execution-flow.md — Step 10`](execution-flow.md#step-10--nexi--xnch-final-verdict-submission-sync)

---

### Step 11 — Execution Dispatch

**Component:** Nexi → execution-runner
**Input:** [`Execution Dispatch Payload`](../reference/data-contracts.md#execution-dispatch-payload) — validated `action_spec` + `execution_token`
**Output:** `execution_ref` (acknowledgement)
**Transformation:** Token validated independently by runner against xnch public key. TTL checked. `action_spec` executed sequentially. Nexi receives `ACCEPTED` immediately; execution is async. → [`execution-flow.md — Step 11`](execution-flow.md#step-11--nexi--execution-layer-dispatch-sync-handoff-async-execution)

---

### Step 12–13 — Execution + Outcome Report

**Component:** execution-runner → xnch-server
**Input:** Completed or failed `action_spec` execution
**Output:** [`Execution Outcome`](../reference/data-contracts.md#execution-outcome)
**Transformation:** Outcome posted to xnch `/execution/outcome`. Token reference validated. Episode completed in Episodic Store. Nexi callback fired. → [`execution-flow.md — Steps 12–13`](execution-flow.md#step-13--execution-layer--xnch-outcome-report-async)

---

### Step 14 — Memory Update

**Component:** xnch-server → memory-store; Nexi → xnch `/memory/write`
**Input:** Execution Outcome + Decision Record reference
**Output:** Completed [`Episode`](../reference/data-contracts.md#episode-learning-record) in Episodic Store
**Transformation:** Episode `completed_at`, `outcome`, `prediction_delta` written. `prediction_delta > 0.3` → early extraction flagged. Write failure handled with exponential backoff. → [`execution-flow.md — Step 14`](execution-flow.md#step-14--xnch--nexi-outcome-callback-async)

---

### Step 15 — Final Delivery

**Component:** xnch-server → Input Layer → Actor
**Input:** Completed episode, execution outcome
**Output:** Final status to actor (`COMPLETED | FAILED`, outcome summary, `audit_ref`)
**Transformation:** Actor receives `audit_ref` for forensic access via `POST /audit/query`. → [`execution-flow.md — Step 15`](execution-flow.md#step-15--xnch--input-layer-final-response-delivery-async)

---

### Loop Closure — Learning Cycle

**Component:** Pattern Extractor, Score Adapter, Policy Candidate Generator (async, scheduled)
**Input:** Accumulated completed episodes
**Output:** Updated patterns in Pattern Store; revised weight configs (xnch-gated); policy candidates queued for review
**Transformation:** 6h schedule or early trigger on high `prediction_delta`. Outputs feed Step 4 (patterns via manifest) and Step 7 (weights) of the next session. → [`components/learning-loop.md`](../components/learning-loop.md)

---

## Data Lifecycle

| Object | Created | Modified | Consumed | Retired |
|--------|---------|----------|----------|---------|
| `Intent` | Step 3 (Nexi) | — | Steps 4, 5, 7 | End of session |
| `Context Manifest` | Step 4 (xnch) | — | Steps 5, 6, 7, 8 | End of session (immutable) |
| `Plan Option` | Step 5 (vLLM via Model Adapter) | Step 6 (MODIFY rewrites spec) | Steps 6, 7, 8 | End of session |
| `Evaluated Option` | Step 7 (Nexi) | Step 8 (re-scored if simulated) | Step 9 | End of session |
| `Decision Record` | Step 9 (Nexi) | — | Steps 10a, 10 (xnch verdict), Audit Logger | Persisted in audit ledger |
| Validated `action_spec` | Step 10a (Plan Compiler) | — | Step 11 (execution-runner) | End of execution |
| `Execution Outcome` | Step 13 (execution-runner) | — | Step 14 (xnch, Nexi) | Persisted in Episode |
| `Episode` | Step 14 (xnch) | Step 14 (completed_at, outcome) | Pattern Extractor (6h cycle) | Retained indefinitely |
| `Pattern` | Learning cycle | Every 6h or early extraction | Step 4 → Step 7 (via manifest) | Superseded by updated version |
| Session state | Step 2 (written to KV Cache) | Step 2a (read) | Step 2 (dedup check) | KV Cache TTL expiry |

---

## Loop Properties

### Continuous Learning

Each completed session produces one episode. Each episode contributes to the pattern store. The pattern store directly feeds `outcome_score` in future evaluations. The loop does not require explicit retraining — improvement is a function of accumulated outcome signal.

### Feedback Incorporation

Feedback enters the loop at two timescales:
- **Per-session (immediate):** `early_reextraction_flag` on `prediction_delta > 0.3` triggers pattern refresh before the next session reaches Step 4.
- **Scheduled (6h):** Full pattern recomputation from all accumulated episodes since last run.

Weights are updated on a third timescale — only when dimension accuracy degrades below 0.6, and only after xnch governance approval.

### State Persistence

All durable state lives in xnch-owned stores (SQLite WAL, sqlite-vec). Session state lives in Redis with TTL. Nexi is stateless between sessions. Episodes and patterns persist indefinitely. Audit ledger entries are immutable once written.

### Idempotency

`idempotency_key` assigned at Step 1. Step 2a KV Cache lookup deduplicates resubmissions within TTL. `decision_id` prevents duplicate audit records on verdict resubmission. Execution outcome posting is keyed on `execution_token_ref`.

### Auditability

Two distinct audit paths run in parallel through every loop iteration:

- **Event Log** (async, all steps): every state transition emits a structured event carrying `trace_id`. Non-blocking. Complete operational record.
- **Decision Ledger** (sync, Step 10 only): the Decision Record is written to a SHA-256 chained JSONL file inside xnch before the verdict response is returned. This is the tamper-evident forensic record.

The `audit_ref` returned to the actor at Step 15 links to the Decision Ledger entry. The `trace_id` links to the full Event Log sequence. Together they provide both forensic integrity and operational observability.

---

## Failure Paths

### Decision Failure

| Failure | Step | Loop Behavior |
|---------|------|--------------|
| Rate limit exceeded | 2a | `429` returned; no session opened; no episode written |
| `ambiguity_score > 0.7` | 3 | Session paused 120s; `CLARIFICATION_REQUIRED` returned; no episode written |
| All options blocked | 6 | `ESCALATED`; hold record written; no token; operator resolves |
| All options simulate to violation | 8 | Same escalation path as Step 6 |
| Plan compilation failure | 10a | Error returned; no verdict call; no episode written |
| xnch final BLOCK | 10 | `ESCALATED`; no retry with next-best option |
| `STALE_SESSION` | 10 | Loop restarts from Step 2 with same `idempotency_key` |

### Execution Failure

| Failure | Step | Loop Behavior |
|---------|------|--------------|
| `TOKEN_EXPIRED` | 11 | Nexi resubmits Decision Record to Step 10 only; same `decision_id` |
| Execution `FAILURE` | 13 | Episode written; pattern extraction flagged; no automatic retry |
| Execution `ROLLED_BACK` | 13 | Same as FAILURE; `observed_state_delta` reflects pre-execution state |
| Memory write failure | 14 | Exponential backoff (5 attempts); episode remains PENDING; background reconciliation |

### Fallback Loop Behavior

When the model layer is unavailable, the loop continues in degraded mode: Step 5 activates the rule-based option generator via the Model Adapter, producing 3 conservative options from policy memory. Steps 6–10 continue normally. `generation_path = RULE_BASED` is recorded in the Decision Record and in the resulting episode, preventing it from biasing pattern extraction for sessions that used normal model generation. → [`runtime.md — Fallback Chain`](runtime.md#fallback-chain-on-gpu-unavailability)
