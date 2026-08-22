# Nexi decision pipeline (API-oriented flow)

The pipeline runs synchronously inside `POST /session/start` in `nexi/main.py`
(except the final callback, which arrives later). Step numbers below match the
code comments in `nexi/main.py`. The xnch control plane drives the loop:
nexi is a **called engine**, not an orchestrator.

```
xnch (actor resolved) ──POST /session/start──▶ nexi
   ◀── SessionStartResponse (EXECUTING) ─────── nexi
   ...execution runner executes...
xnch ──POST /callback/outcome──▶ nexi  (Step 14)
xnch ◀── {"status":"ok"} ──────── nexi  (after /memory/write)
```

## Stage map

| Step | Stage | Module / function | HTTP dependency |
|------|-------|-------------------|-----------------|
| (1) | xnch resolves actor | *(xnch side)* | — |
| (2→3) | `POST /session/start` received | `nexi/main.py:session_start` | — |
| 3 | Intent interpretation | `pipeline/intent_interpreter.py::IntentInterpreter.interpret` | LiteLLM `POST /chat/completions` (fallback only); Redis `xnch:intent:<sha256>` cache |
| 3a | Injection scan | `xnch.security.injection_guard.scan_input` | — (raises `PolicyViolation`) |
| 4 | Context manifest | `pipeline/context_loader.py::load_context` → `XnchClient.read_context` | xnch `POST /memory/read` (hard stop on failure → 503) |
| 4a | Weight config | `XnchClient.get_weight_config` | xnch `GET /governance/weights?intent_class=` (optional) |
| 5 | Option generation | `pipeline/option_generator.py::generate_options` → `ModelAdapter.generate_options` | LiteLLM → vLLM → llama.cpp → rule-based fallback |
| 6 | Policy dry-run | `pipeline/policy_filter.py::PolicyFilter.filter` → `check_policies_parallel` | xnch `POST /policy/check` per option (parallel) |
| 7 | Scoring | `pipeline/evaluator.py::Evaluator.score` | — |
| 8 | Outcome simulation (conditional) | `Evaluator.simulate_and_rescore` | — (v0 stub: `_project_state` returns no violation) |
| 9 | Selection | `pipeline/selector.py::select_decision` | — |
| 10a | Plan compilation | `pipeline/plan_compiler.py::compile_action_spec` | — (→ single-node `CompiledDAG`, 422 on failure) |
| 10 | Verdict | `XnchClient.submit_verdict` | xnch `POST /verdict` (502 on failure; `STALE_SESSION` ⇒ reload context + retry once, else 409) |
| 11 | Execution dispatch | `pipeline/dispatch.py::dispatch_execution` | runner `POST {NEXI_EXECUTION_RUNNER_URL}/execute` |
| 12 | Intermediate response | `session_start` returns | — (`EXECUTING`) |
| 14 | Outcome callback | `nexi/main.py:outcome_callback` | xnch `POST /memory/write` (prediction delta) |

## Stage detail

### Step 3 — Intent interpretation (`intent_interpreter.py`)
1. Compute `raw_input_hash = "sha256:" + sha256(raw_input)`.
2. **Injection scan** via `xnch.security.injection_guard.scan_input`; dirty input
   raises `PolicyViolation` (currently uncaught → 500 in `/session/start`).
3. **Rule pre-filter** — regex table maps leading verbs to
   `(IntentClass, ActionType)` with confidence 1.0, ambiguity 0.0
   (e.g. `list|show all` → `QUERY/LIST`, `deploy|launch` → `EXECUTION/DEPLOY`).
4. **Redis cache** — key `xnch:intent:<sha256(lowercased input)>`, TTL 7 days;
   a hit returns the stored `Intent`.
5. **LiteLLM classifier** — `POST {NEXI_LITELLM_PROXY_URL}/chat/completions`
   with `response_format: json_object`, model `NEXI_INTENT_CLASSIFIER_MODEL`.
   Parsed JSON: `intent_class`, `action_type`, `entity_class`, `urgency`,
   `entity_id`, `clarifications_needed[]`. Non-empty clarifications raise
   `ClarificationRequired` → `status=CLARIFICATION_REQUIRED`.
6. **Fallback** — on LLM failure, downgrades to `QUERY/ANALYZE` (ambiguity 0.5).
7. Caches the result in Redis; emits audit events (`CLASSIFY_START`,
   `INTENT_CLASSIFIED`, `LLM_CLASSIFY_FAILED`, …).

### Step 4 — Context manifest (`context_loader.py`)
- `XnchClient.read_context` posts to xnch `/memory/read` with
  `{session_id, actor_id, actor_role, query:{intent_class, target_entity_id,
  target_entity_class, lookback_window_days:30, max_episodes:20, max_patterns:10}}`.
- Returns `ContextManifest` (episodes/patterns/policies).
- **Hard stop**: any failure → HTTP 503 `DEGRADED: context manifest unavailable`.
  No empty-context fallback by design.

### Step 4a — Weight config (optional)
- `GET {XNCH_BASE_URL}/governance/weights?intent_class=…`; on failure nexi falls
  back to `_DEFAULT_WEIGHTS` in `evaluator.py`. Shipped local profiles in
  `nexi/weights/` (EXECUTION / QUERY, `wc-v1.0`).

### Step 5 — Option generation (`option_generator.py` / `model_adapter.py`)
- Primary: `generate_options` calls LiteLLM directly with a system prompt and
  context summary (`recent_outcomes` "S/P/F", `dominant_pattern`), requesting
  exactly `NEXI_OPTIONS_COUNT` (default 5) options as `{"options":[...]}` JSON.
- If LiteLLM fails, `ModelAdapter.generate_options` retries:
  1. LiteLLM proxy (`NEXI_LITELLM_PROXY_URL`)
  2. vLLM primary (`NEXI_VLLM_PRIMARY_URL`)
  3. llama.cpp (`http://localhost:8080`)
  4. **Rule-based templates** per `IntentClass` (never produces
     `RUN_COMMAND/RUN_SCRIPT/DEPLOY/ROLLBACK/DELETE_FILE/MUTATE` in fallback).
- Result tagged with `GenerationPath` (`MODEL` / `RULE_BASED`), each option has a
  `sha256:` `payload_hash` of its canonical action spec.
- Emits audit events `GENERATION_START`, `GENERATION_COMPLETE`.

### Step 6 — Policy dry-run (`policy_filter.py`)
- `check_policies_parallel` fans out `POST /policy/check` for every option
  (`asyncio.gather`).
- `PolicyVerdict.BLOCK` options are dropped. `MODIFY` verdicts replace the option's
  `action_spec` with xnch's `modified_action_spec`.
- If **all** options are blocked → `AllOptionsBlocked` → `status=ESCALATED`
  with a new `hold_id`.

### Steps 7 & 8 — Scoring + simulation (`evaluator.py`)
- **Step 7** `Evaluator.score`: per option computes four 0–1 scores and a
  weighted composite:
  - `policy_score` ← verdict map (`ALLOW` 1.0, `ALLOW_WITH_WARNINGS` 0.7, `MODIFY` 0.5, `DEFER` 0.3)
  - `outcome_score` ← matched `ContextManifest.patterns` success_rate × confidence (else 0.5)
  - `risk_score` ← irreversibility + entity sensitivity + side-effect count + AGENT role
  - `context_fit_score` ← constraint coverage (1.0 if no constraints)
  - weights from xnch `/governance/weights` (or `_DEFAULT_WEIGHTS`)
  - `simulation_required` when risk > 0.6, irreversible, or actor is AGENT
- **Step 8** `simulate_and_rescore`: top-2 simulated options get risk +0.3 and a
  recomputed composite if `_project_state` flags a violation. **v0 stub always
  returns False (no violation)** — real forward projection is a TODO.

### Step 9 — Selection (`selector.py`)
- Ranks evaluated options by `composite_score`; picks best.
- `confidence = best − runner_up` (0.0 if only one).
- Builds `DecisionRecord` (options_generated, options_blocked, rationale,
  `generation_path`). Escalates (`escalation_triggered=True`, no selection) when
  no options ranked.

### Step 10a — Plan compilation (`plan_compiler.py`)
- Validates selected `ActionSpec` (type/target/params non-null) → 422
  `PlanCompilationError` on failure.
- Returns a **single-node** `CompiledDAG` (`node_id = option_id`, empty edges).
  Empty DAG → 422.

### Step 10 — Verdict (`XnchClient.submit_verdict`)
- `POST /verdict` with:
  - `request_id = decision_id`
  - `actor {id, claimed_role}`
  - `action {type, target, payload_hash, payload, intent_class, entity_class}`
  - `context {session_id, nexi_reasoning_ref: decision_id, system_state_version, outcome_score_predicted}`
- `VerdictResponse` contains `verdict` (`BLOCK` → `ESCALATED`+hold_id), `execution_token`,
  `token_ttl_ms`, `audit_ref`.
- **STALE_SESSION**: on `STALE_SESSION` in the error body, nexi re-loads the
  manifest for a fresh `system_state_version`, updates the session, and
  resubmits once. Retry failure → 409.

### Step 11 — Dispatch (`dispatch.py`)
- Requires `verdict.execution_token`; builds `ExecutionDispatchPayload`
  (`execution_ref`, `trace_id`, `decision_id`, `action_spec`,
  `execution_token`, `token_ttl_ms`).
- `POST {NEXI_EXECUTION_RUNNER_URL}/execute`.
  - `401 TOKEN_EXPIRED` → nexi re-submits verdict to xnch for a new token, then
    dispatches again.
  - `httpx.ConnectError` → runner unavailable: logs, emits
    `EXECUTION_DEFERRED`, and **records a stub SUCCESS outcome** to xnch
    `POST /execution/outcome` so the loop still closes.

### Step 12 — Intermediate response
- Returns `SessionStartResponse(status="EXECUTING", decision_id, execution_ref,
  estimated_completion_ms, audit_ref)`. `estimated_completion_ms` = mean
  `duration_ms` of completed manifest episodes (30s fallback).

### Step 14 — Outcome callback (`/callback/outcome`)
- xnch fires this after writing the execution outcome to its episodic store.
- nexi computes `prediction_delta = |outcome_score_predicted − actual|` and
  `early_flag = delta > 0.3`, then writes to xnch
  `POST /memory/write` (`write_type: EPISODE_PREDICTION_UPDATE`).
- Always returns `{"status":"ok"}`; memory-write failures are logged and left to
  the caller to retry (TODO: exponential backoff, max 5 attempts).

## Which stages are HTTP-exposed

Only the five routes in [endpoints.md](endpoints.md) are HTTP. Every decision
pipeline stage above runs **inside** `POST /session/start` — there is no
per-stage HTTP surface (no `/pipeline/score`, `/pipeline/select`, etc.). The
`/nexi/capabilities` and `/nexi/refresh` routes expose the *capability/infra
awareness* loop (`nexi/infra/discovery.py` + `nexi/character/capability_builder.py`),
not the decision pipeline.

## How the pipeline calls xnch

All xnch calls go through `nexi/adapters/xnch_client.py::XnchClient`
(`base_url = settings.xnch_base_url`, 10s timeout):

| nexi stage | xnch endpoint |
|------------|---------------|
| Step 4 context | `POST /memory/read` |
| Step 4a weights | `GET /governance/weights` |
| Step 6 policy | `POST /policy/check` (parallel) |
| Step 10 verdict | `POST /verdict` |
| Step 11 stub outcome | `POST /execution/outcome` |
| Step 14 delta | `POST /memory/write` |
