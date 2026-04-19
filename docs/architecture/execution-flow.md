---
source: runtimeExecFlow.md
merged: 2026-04-18
---

# Runtime Execution Flow

## 1. Step-by-Step Execution Flow

---

### PHASE A: INGESTION

#### Step 1 — Input Layer receives raw input [SYNC]

CLI/API gateway receives user input. Performs only transport-level validation: auth token present, payload size within limit, content-type valid. No semantic parsing here.

Assigns `trace_id` and `idempotency_key`. Forwards immediately to xnch.

Caller: Input Layer → xnch `POST /session/init`

---

#### Step 2 — xnch: Session initialization + actor resolution [SYNC]

xnch receives the session init request. Does three things in order, all blocking:

1. Verifies auth token signature. Extracts `actor_id`.
2. Resolves `actor_id` → `role` + `capability_set` from internal governance store. Does NOT trust claimed role in request.
3. Calls `GET /system/state` internally. Pins `system_state_version` and `policy_version` to this session.

Returns `session_context` to input layer, which forwards it to Nexi with the original request.

Caller: xnch → Nexi `POST /session/start`

---

### PHASE B: INTENT + CONTEXT

#### Step 3 — Nexi: Intent interpretation [SYNC]

Nexi receives raw input + session context. Intent Interpreter normalizes:
- Classifies `intent_class`
- Identifies `target_entity_id` and `target_entity_class`
- Computes `ambiguity_score`

If `ambiguity_score > 0.7`: **STOP**. Return `CLARIFICATION_REQUIRED` to input layer with structured question. Session stays open, waiting.

If clear: proceed to Step 4.

---

#### Step 4 — Nexi → xnch: Context manifest request [SYNC]

Nexi calls `POST /memory/read` on xnch with a targeted query. xnch evaluates read policy against actor capability, then queries all three memory stores in parallel:

- Episodic store: last 20 episodes matching `(intent_class, entity_class, actor_role)` within lookback window
- Semantic store: top 10 patterns by confidence matching same tuple
- Policy store: all active policies scoped to `(intent_class, entity_class, actor_role)`

xnch assembles and returns the context manifest. Nexi pins it. This snapshot is immutable for this session.

---

### PHASE C: OPTION GENERATION

#### Step 5 — Nexi → Model Layer: Constrained generation request [SYNC]

Nexi constructs a structured prompt. Not freeform. Template-driven, versioned. Contains:
- Normalized intent object
- Relevant context subset (entity history summary, not raw episodes)
- Output schema: must return exactly N structured options (default N=5)
- Explicit instruction: generate only, do not evaluate, do not select

Model layer returns raw option set. Nexi validates schema. If malformed: retry once with stricter prompt. If second failure: fall back to rule-based option generator (produces conservative default options from policy memory).

---

#### Step 6 — Nexi → xnch: Parallel policy dry-run [SYNC, parallel fanout]

Nexi fires `GET /policy/check` for all N options simultaneously. xnch evaluates each against active policy set.

Returns per option: `ALLOW | ALLOW_WITH_WARNINGS | MODIFY | DEFER | BLOCK`

- `BLOCK` options: dropped from candidate set immediately
- `MODIFY` options: action spec replaced with xnch's modified version, flagged
- `DEFER` options: retained but marked, require secondary auth before execution token issuance
- `ALLOW` / `ALLOW_WITH_WARNINGS`: proceed to scoring

If all options return `BLOCK`: Nexi escalates. Does not force selection. Returns `ESCALATED` status with hold record to xnch.

---

### PHASE D: EVALUATION + SELECTION

#### Step 7 — Nexi: Option scoring [SYNC]

For each surviving option, Option Evaluator computes four scores in parallel:

- `policy_score`: derived from Step 6 verdict
- `outcome_score`: pattern lookup against semantic memory (already in manifest from Step 4). Applies recency adjustment against episodic history.
- `risk_score`: computed from action reversibility + entity sensitivity + side effect count + actor type
- `context_fit_score`: structural field coverage ratio between option spec and intent constraints

Composite score computed with intent-class-specific weights (loaded from policy memory in manifest).

---

#### Step 8 — Nexi: Outcome simulation (conditional) [SYNC]

Triggered if: any surviving option has `risk_score > 0.6`, OR `intent_class = EXECUTION` with irreversible flag, OR `actor.type = AGENT`.

Runs forward state projection for top 2 options only (by composite score so far). Uses current system state snapshot + outcome_delta patterns from episodic memory.

If projected state violates any loaded policy: re-score with `risk_score += 0.3` penalty.

If all projected states violate constraints: escalate, do not select.

---

#### Step 9 — Nexi: Decision selection + record assembly [SYNC]

Highest composite score, non-blocked, non-escalated option is selected.

Nexi assembles full decision record:
```
decision_record {
  decision_id, session_id, intent_ref,
  context_manifest_ref, system_state_version,
  options_generated, options_blocked,
  options_evaluated: [{ option_id, policy_score, outcome_score,
                        risk_score, context_fit_score, composite }],
  selected_option_id,
  selection_rationale: { score_breakdown, weight_config_version },
  confidence: selected.composite - second_best.composite,  // margin
  escalation_triggered: false
}
```

---

### PHASE E: AUTHORIZATION

#### Step 10 — Nexi → xnch: Final verdict submission [SYNC]

Nexi calls `POST /verdict` with the full decision record as payload.

xnch performs final evaluation:
1. Verifies `system_state_version` in decision record matches current pinned version. If mismatch: `REJECT`, session must restart.
2. Re-evaluates selected action against policy (not dry-run — this is the authoritative check).
3. Verifies actor capability covers this action type.
4. Emits audit record (synchronous, before response returned).
5. Issues signed execution token with TTL.

Returns verdict response to Nexi including `execution_token`.

---

### PHASE F: EXECUTION

#### Step 11 — Nexi → Execution Layer: Dispatch [SYNC handoff, ASYNC execution]

Nexi passes to execution layer:
- `action_spec` (final, post-MODIFY if applicable)
- `execution_token` (xnch-signed JWT)
- `trace_id`

Execution layer validates token signature independently — does not trust Nexi's word that xnch approved it. Checks token TTL. If expired (can happen if scoring took too long): rejects, Nexi must resubmit to xnch for new token.

Execution begins. This step is async — Nexi does not block waiting for execution to complete. Returns `ACCEPTED` with `execution_ref` to Nexi immediately.

---

#### Step 12 — Nexi → Input Layer: Intermediate response [SYNC]

While execution runs async, Nexi returns to the user:
```
{
  status: EXECUTING,
  decision_id,
  execution_ref,
  estimated_completion_ms,  // from pattern history avg_execution_ms
  audit_ref                 // user can query decision reasoning via this
}
```

---

#### Step 13 — Execution Layer → xnch: Outcome report [ASYNC]

On completion (success or failure), execution layer posts outcome to xnch:
```
POST /execution/outcome {
  execution_ref, decision_id, execution_token_ref,
  outcome_status: SUCCESS | PARTIAL | FAILURE | ROLLED_BACK,
  observed_state_delta: { ... },
  side_effects_observed: [ ... ],
  duration_ms,
  anomalies: [ ... ]
}
```

xnch validates token ref matches a known issued token. Writes `outcome_status`, `observed_state_delta`, `side_effects_observed`, `duration_ms`, and `anomalies` to the episodic store, marking the episode `COMPLETE`. xnch is the sole writer of these fields. Triggers Nexi callback.

---

#### Step 14 — xnch → Nexi: Outcome callback [ASYNC]

xnch fires callback to Nexi with outcome payload. Nexi:
1. Computes `prediction_delta` (`abs(outcome_score_predicted - actual_success_rate)`) and sets `early_reextraction_flag` if delta > 0.3.
2. Calls `POST /memory/write` on xnch with `prediction_delta` and `early_reextraction_flag` only. xnch appends these two fields to the already-complete episode record. Nexi does not write outcome fields — those were written by xnch at Step 13. xnch is the single writer of the episode at all phases.

---

#### Step 15 — xnch → Input Layer: Final response delivery [ASYNC]

xnch pushes final outcome to input layer (via websocket/SSE/polling depending on transport). Input layer delivers to user:
```
{
  status: COMPLETED | FAILED,
  outcome_summary: string,
  execution_ref,
  decision_id,
  audit_ref
}
```

---

## 2. Example: "deploy model llama3-8b to inference cluster"

```
Step 1:  CLI receives: "deploy model llama3-8b to inference cluster"
         Assigns: trace_id=tr_8a2f, idempotency_key=ik_991c
         Auth token: Bearer eyJ...

Step 2:  xnch resolves actor_id=pavan → role=OPERATOR
         capability_set=[DEPLOY, READ, QUERY]
         system_state_version=v3.2.1, policy_version=v2.0.4
         Session pinned.

Step 3:  Nexi interprets:
         intent_class=EXECUTION
         target_entity_id=llama3-8b
         target_entity_class=ML_MODEL
         action_hint=DEPLOY
         ambiguity_score=0.12  → proceed

Step 4:  Memory read returns:
         episodes: 8 prior DEPLOY actions on ML_MODEL class
           - 6 SUCCESS, 1 PARTIAL (OOM on node), 1 FAILURE (image pull timeout)
         patterns: 2 active
           - DEPLOY + ML_MODEL + OPERATOR → success_rate=0.75, confidence=0.61
           - DEPLOY + ML_MODEL + large_model_flag → success_rate=0.50, confidence=0.40
         policies: 4 active
           - ml.deploy.require_resource_check (CONDITIONAL)
           - ml.deploy.gpu_node_only (HARD_BLOCK if CPU target)
           - ml.deploy.max_replicas_3 (MODIFY if replicas > 3)
           - infra.execution.operator_allowed (ALLOW)

Step 5:  Model generates 5 options:
         A: deploy llama3-8b, 1 replica, gpu-node-01, resource_check=true
         B: deploy llama3-8b, 2 replicas, gpu-node-01+02, resource_check=true
         C: deploy llama3-8b, 1 replica, auto-select node, resource_check=false
         D: deploy llama3-8b, 4 replicas, auto-select, resource_check=true
         E: stage llama3-8b to registry only, no cluster deployment

Step 6:  Policy dry-run results:
         A → ALLOW (clean)
         B → ALLOW_WITH_WARNINGS (node-02 near capacity)
         C → MODIFY (resource_check forced to true by ml.deploy.require_resource_check)
         D → MODIFY (replicas reduced 4→3 by ml.deploy.max_replicas_3) + ALLOW_WITH_WARNINGS
         E → ALLOW (clean)

Step 7:  Scoring (EXECUTION intent_class weights: risk=0.35, outcome=0.30, policy=0.25, context=0.10):
         A: policy=1.0, outcome=0.75*0.61=0.46, risk=0.55(irreversible+ML_MODEL sensitive), context=0.90 → composite=0.68
         B: policy=0.7, outcome=0.46, risk=0.65, context=0.85 → composite=0.62
         C: policy=0.5, outcome=0.46, risk=0.55, context=0.70 → composite=0.55
         D: policy=0.5, outcome=0.46, risk=0.70, context=0.75 → composite=0.55
         E: policy=1.0, outcome=0.30(pattern mismatch-partial), risk=0.10, context=0.40 → composite=0.52

         Recency check: last 3 DEPLOY+ML_MODEL episodes = 2 SUCCESS, 1 PARTIAL → no penalty

Step 8:  Simulation triggered: EXECUTION + irreversible flag
         Option A projected state: gpu-node-01 VRAM utilization 18GB/24GB → within bounds
         Option B projected state: gpu-node-02 VRAM at 22GB/16GB → CONSTRAINT VIOLATION
         Option B re-scored: risk += 0.3 → composite drops to 0.41

         Final ranking: A(0.68) > B(0.41) > C(0.55) > D(0.55) > E(0.52)
         Winner: Option A

Step 9:  Decision record assembled. confidence = 0.68 - 0.55 = 0.13 (low margin, noted)

Step 10: xnch final verdict:
         system_state_version match: v3.2.1 ✓
         Re-evaluation: ALLOW
         Audit record emitted: audit_id=aud_3b9f
         Execution token issued: TTL=30000ms

Step 11: Execution layer receives action_spec + token
         Token validated. TTL check: 28400ms remaining ✓
         Begins: kubectl apply -f llama3-8b-deploy.yaml --namespace inference

Step 12: User receives: { status: EXECUTING, decision_id: dec_77a1,
                          execution_ref: exec_cc20, estimated_completion_ms: 45000 }

Step 13: Execution completes in 38200ms.
         outcome_status: SUCCESS
         observed_state_delta: { pod: llama3-8b-xxx RUNNING, vram_allocated: 18GB }
         side_effects: [ingress_route_registered, metrics_scrape_target_added]

Step 14: Nexi receives callback.
         outcome_score prediction was 0.46, actual = SUCCESS → delta = 0.54
         Delta > 0.3 → flags DEPLOY+ML_MODEL pattern for early re-extraction.
         Memory write: episode completed, decision outcome recorded.

Step 15: User receives: { status: COMPLETED, outcome_summary: "llama3-8b deployed,
                          1 replica running on gpu-node-01, VRAM: 18GB/24GB" }
```

---

## 3. Data Contracts Between Steps

```javascript
// Step 1 → Step 2: Input Layer → xnch /session/init
{
  trace_id: "tr_8a2f",
  idempotency_key: "ik_991c",
  auth_token: "Bearer eyJ...",
  raw_input: "deploy model llama3-8b to inference cluster",
  input_type: "TEXT",
  priority: "NORMAL",
  source_system: "cli-v1.4"
}

// Step 2 → Step 3: xnch → Nexi /session/start
{
  session_id: "sess_b31d",
  trace_id: "tr_8a2f",
  actor: { id: "pavan", role: "OPERATOR", capability_set: ["DEPLOY","READ","QUERY"] },
  system_state_version: "v3.2.1",
  policy_version: "v2.0.4",
  raw_input: "deploy model llama3-8b to inference cluster",
  priority: "NORMAL"
}

// Step 3 → Step 4: Nexi → xnch /memory/read
{
  session_id: "sess_b31d",
  actor_id: "pavan",
  actor_role: "OPERATOR",
  query: {
    intent_class: "EXECUTION",
    target_entity_id: "llama3-8b",
    target_entity_class: "ML_MODEL",
    lookback_window_days: 30,
    max_episodes: 20,
    max_patterns: 10
  }
}

// Step 4 → Step 5: manifest returned to Nexi (internal)
{
  manifest_id: "mfst_44e2",
  system_state_version: "v3.2.1",
  episodes: [ { episode_id, action_type, outcome, created_at, ... } ],
  patterns: [ { pattern_id, success_rate, confidence, context_signature, ... } ],
  policies: [ { policy_id, rule_expression, enforcement_level, ... } ]
}

// Step 5: Nexi → Model Layer (prompt payload, internal)
{
  template_version: "gen-v2.1",
  intent: { class: "EXECUTION", entity_id: "llama3-8b", entity_class: "ML_MODEL" },
  context_summary: { recent_outcomes: "6S/1P/1F", dominant_pattern: "0.75 success" },
  output_schema: { type: "array", items: { option_id, action_type, action_spec,
                stated_rationale, estimated_side_effects }, minItems: 3, maxItems: 7 },
  instruction: "Generate only. Do not evaluate. Do not select."
}

// Step 6: Nexi → xnch /policy/check (per option, parallel)
{
  session_id: "sess_b31d",
  system_state_version: "v3.2.1",
  actor_role: "OPERATOR",
  option_id: "opt_A",
  action: {
    type: "DEPLOY",
    target: "llama3-8b",
    spec: { replicas: 1, node: "gpu-node-01", resource_check: true },
    payload_hash: "sha256:a1b2..."
  }
}

// Step 10: Nexi → xnch /verdict
{
  request_id: "req_f20a",
  actor: { id: "pavan", claimed_role: "OPERATOR" },
  action: {
    type: "DEPLOY",
    target: "llama3-8b",
    payload_hash: "sha256:a1b2...",
    payload: { replicas: 1, node: "gpu-node-01", resource_check: true }
  },
  context: {
    session_id: "sess_b31d",
    nexi_reasoning_ref: "dec_77a1",
    system_state_version: "v3.2.1"
  }
}

// Step 10 response: xnch → Nexi
{
  request_id: "req_f20a",
  verdict: "ALLOW",
  verdict_reason: "all policies satisfied",
  policy_refs: ["infra.execution.operator_allowed", "ml.deploy.require_resource_check"],
  modified_action: null,
  execution_token: "eyJ...signed_jwt...",
  token_ttl_ms: 30000,
  audit_ref: "aud_3b9f"
}

// Step 11: Nexi → Execution Layer
{
  execution_ref: "exec_cc20",
  trace_id: "tr_8a2f",
  decision_id: "dec_77a1",
  action_spec: { type: "DEPLOY", target: "llama3-8b",
                 params: { replicas: 1, node: "gpu-node-01", resource_check: true } },
  execution_token: "eyJ...signed_jwt...",
  token_ttl_ms: 30000
}

// Step 13: Execution Layer → xnch /execution/outcome
{
  execution_ref: "exec_cc20",
  decision_id: "dec_77a1",
  execution_token_ref: "eyJ...signed_jwt...",
  outcome_status: "SUCCESS",
  observed_state_delta: { pod: "llama3-8b-7f9d", status: "RUNNING",
                          node: "gpu-node-01", vram_allocated_gb: 18 },
  side_effects_observed: ["ingress_route_registered", "metrics_scrape_target_added"],
  duration_ms: 38200,
  anomalies: []
}

// Step 14: Nexi → xnch /memory/write
// Nexi sends prediction fields only. Outcome fields were already written by xnch at Step 13.
{
  session_id: "sess_b31d",
  actor_id: "pavan",
  write_type: "EPISODE_PREDICTION_UPDATE",
  payload: {
    episode_id: "ep_5512",
    prediction_delta: 0.54,
    early_reextraction_flag: true
  }
}
```

---

## 4. Where Latency Occurs

```
Step 2   — xnch actor resolution         ~20–50ms      governance store lookup
Step 4   — Memory read (manifest)        ~80–200ms     3 parallel store queries + assembly
Step 5   — Model generation              ~800–4000ms   DOMINANT: LLM inference latency
Step 6   — Parallel policy dry-run       ~40–120ms     N parallel xnch evaluations
Step 7   — Option scoring                ~10–30ms      in-memory computation, negligible
Step 8   — Outcome simulation            ~30–80ms      conditional, pattern lookup + projection
Step 10  — xnch final verdict            ~30–60ms      policy eval + audit write + token sign
Step 11  — Execution dispatch            ~10ms         handoff only, execution is async
Step 13  — Execution itself              ~5000–60000ms DOMINANT: real-world operation
```

**Total pre-execution latency (Steps 1–12): ~1100–4600ms.** Model generation accounts for 70–85% of that. Every other component is fast. Optimizing anything other than Step 5 has marginal return unless model latency is already minimized.

**Optimization levers:**
- Step 5: Use local inference (vLLM on your RTX 3090) to cut model latency to ~200–600ms
- Step 4: Cache context manifests for repeat entity+intent combinations with a short TTL (60s)
- Step 6: Run policy dry-run in parallel (already specified), not sequential

---

## 5. Failure Modes and Handling

```
Step 2 — Actor resolution failure
  Cause:   governance store unavailable, or unknown actor_id
  Handle:  xnch returns 401/503. Input layer returns auth error to user.
           Session never opens. No state written.

Step 3 — High ambiguity
  Cause:   ambiguity_score > 0.7
  Handle:  Nexi returns CLARIFICATION_REQUIRED. Session stays open with TTL=120s.
           If no clarification received within TTL: session auto-closes, no episode written.

Step 4 — Memory read failure
  Cause:   xnch memory store unavailable
  Handle:  Nexi cannot load context manifest. Hard stop.
           Returns DEGRADED status. Does not proceed with empty context.
           Rationale: reasoning without context produces unreliable options.
           No fallback to "proceed anyway" — this is a deliberate design choice.

Step 5 — Model layer failure (both attempts)
  Cause:   Model timeout, schema validation failure on retry
  Handle:  Nexi activates rule-based option generator.
           Produces 3 conservative options from policy memory directly.
           Options flagged as RULE_GENERATED in decision record.
           Audit record notes degraded generation path.

Step 6 — All options blocked
  Cause:   Policy set blocks every generated option
  Handle:  Nexi escalates. Writes hold record to xnch.
           Returns ESCALATED to user with hold_id and required_actor (e.g. ADMIN).
           No execution token issued. Session preserved for admin resolution.

Step 8 — All options simulate to constraint violation
  Cause:   System state + all action types project to bad state
  Handle:  Same as Step 6 escalation path. Nexi does not select under duress.

Step 10 — System state version mismatch
  Cause:   Policy updated between session init (Step 2) and verdict submission (Step 10)
  Handle:  xnch rejects with STALE_SESSION. Nexi must restart from Step 2.
           Idempotency key prevents duplicate episode creation on restart.
           Common cause: admin deployed new policy mid-session.

Step 10 — xnch final verdict = BLOCK (overrides dry-run ALLOW)
  Cause:   Race condition — policy changed between dry-run (Step 6) and final verdict
           OR dry-run evaluated subset, final verdict caught additional policy
  Handle:  Nexi escalates. Does not retry with next-best option automatically.
           Rationale: if xnch blocked after dry-run passed, something changed.
           Automatic retry could be selecting the second-best option into the same block.
           Human review required.

Step 11 — Execution token TTL expired before dispatch
  Cause:   Scoring + simulation took longer than token TTL (30s)
  Handle:  Execution layer rejects with TOKEN_EXPIRED. Nexi resubmits to
           xnch /verdict with same decision_id. xnch re-evaluates and issues
           new token. Idempotency key on decision_id prevents duplicate audit records.

Step 13 — Execution FAILURE or ROLLED_BACK
  Cause:   Real-world operation failed (OOM, image pull timeout, etc.)
  Handle:  Execution layer reports outcome. xnch writes episode with FAILURE outcome.
           Nexi receives callback. Pattern extraction flagged for early run.
           Episode contributes to lowering outcome_score for this action/entity pattern.
           User receives FAILED status with anomaly details.
           No automatic retry — retry is a new session, new decision cycle.

Step 14 — Memory write failure (outcome registration)
  Cause:   xnch memory store unavailable at callback time
  Handle:  Nexi queues the write locally with exponential backoff retry (max 5 attempts).
           Execution already completed — this failure does not affect the user outcome.
           The episode is already COMPLETE in the episodic store (written by xnch at Step 13);
           only `prediction_delta` and `early_reextraction_flag` are missing.
           If all retries fail: emit alert. Episode persists as COMPLETE but without prediction
           fields; it is excluded from Score Adapter accuracy tracking until resolved.
           Background reconciliation job detects episodes with null `prediction_delta` after
           TTL and flags for manual resolution. This is the only step where eventual
           consistency is acceptable because it affects future learning, not current execution.
```