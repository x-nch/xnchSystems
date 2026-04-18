# Data Contracts

---
tags:
  - #reference
  - #contracts
  - #data
---

All core data structures exchanged across xnch + Nexi component boundaries. Consistent with [[execution-flow.md]].

For field-level schema definitions, see [[schemas/index.md]].

---

## Intent

Produced by: Nexi — Intent Interpreter (Step 3)
Consumed by: Nexi — Option Generator, Context Loader

```json
{
  "intent_id": "uuid",
  "session_id": "uuid",
  "intent_class": "QUERY | DECISION | EXECUTION | ESCALATION",
  "target_entity": "string",
  "target_entity_class": "string",
  "constraints_declared": ["string"],
  "urgency": "LOW | NORMAL | HIGH | CRITICAL",
  "ambiguity_score": 0.12,
  "raw_input_hash": "sha256:..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `intent_id` | UUID | Yes | Unique ID for this interpretation result |
| `session_id` | UUID | Yes | Parent session reference |
| `intent_class` | enum | Yes | Coarse classification; determines evaluation weight profile |
| `target_entity` | string | Yes | Specific entity being acted upon (e.g., `llama3-8b`) |
| `target_entity_class` | string | Yes | Entity type (e.g., `ML_MODEL`, `SERVICE`, `DATABASE`) |
| `constraints_declared` | string[] | No | Explicit constraints extracted from input |
| `urgency` | enum | Yes | Affects risk weight profile in evaluation |
| `ambiguity_score` | float [0,1] | Yes | Above 0.7: session halts, returns `CLARIFICATION_REQUIRED` |
| `raw_input_hash` | sha256 | Yes | Hash of the original raw input string; used for idempotency |

---

## Context Manifest

Produced by: xnch — memory read response (Step 4)
Consumed by: Nexi — Option Generator, Option Evaluator

```json
{
  "manifest_id": "uuid",
  "session_id": "uuid",
  "system_state_version": "v3.2.1",
  "pinned_at": "2026-04-18T10:30:00Z",
  "episodes": [
    {
      "episode_id": "uuid",
      "action_type": "DEPLOY",
      "entity_class": "ML_MODEL",
      "outcome": "SUCCESS | PARTIAL | FAILURE",
      "created_at": "iso8601"
    }
  ],
  "patterns": [
    {
      "pattern_id": "uuid",
      "context_signature": "sha256:...",
      "success_rate": 0.75,
      "confidence": 0.61,
      "observation_count": 42
    }
  ],
  "policies": [
    {
      "policy_id": "string",
      "rule_expression": "string",
      "enforcement_level": "HARD_BLOCK | CONDITIONAL | MODIFY | DEFER"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `manifest_id` | UUID | Yes | Unique ID for this context snapshot |
| `system_state_version` | string | Yes | Must match at verdict submission; mismatch causes `STALE_SESSION` |
| `pinned_at` | iso8601 | Yes | Time this snapshot was assembled; manifest is immutable after this |
| `episodes` | array | Yes | Last ≤20 episodes matching `(intent_class, entity_class, actor_role)` within lookback window |
| `patterns` | array | Yes | Top ≤10 patterns by confidence matching same tuple |
| `policies` | array | Yes | All active policies scoped to `(intent_class, entity_class, actor_role)` |

---

## Plan Option

Produced by: vLLM (via Nexi — Option Generator) (Step 5)
Consumed by: Nexi — Policy Alignment Filter, Option Evaluator

```json
{
  "option_id": "uuid",
  "action_type": "DEPLOY | QUERY | MUTATE | ROLLBACK | STAGE",
  "action_spec": {
    "target": "string",
    "params": {}
  },
  "stated_rationale": "string",
  "estimated_side_effects": ["string"],
  "reversible": true,
  "payload_hash": "sha256:..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `option_id` | UUID | Yes | Unique per option within the session |
| `action_type` | enum | Yes | Determines risk profile and policy matching |
| `action_spec` | object | Yes | Structured action parameters; schema is action-type specific |
| `stated_rationale` | string | Yes | Model-supplied reasoning; used for audit record only, not for scoring |
| `estimated_side_effects` | string[] | Yes | Model-declared side effects; used in risk scoring |
| `reversible` | bool | Yes | If false, triggers Outcome Simulator unconditionally |
| `payload_hash` | sha256 | Yes | Hash of `action_spec`; used for tamper detection at execution token issuance |

Minimum viable option set: 3. Maximum: 7. The model is instructed to generate exactly N (configured default: 5).

---

## Policy Dry-Run Response

Produced by: xnch — `/policy/check` (Step 6)
Consumed by: Nexi — Policy Alignment Filter

```json
{
  "option_id": "uuid",
  "session_id": "uuid",
  "verdict": "ALLOW | ALLOW_WITH_WARNINGS | MODIFY | DEFER | BLOCK",
  "policy_refs": ["policy_id"],
  "warnings": ["string"],
  "modified_action_spec": null,
  "requires_actor": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `verdict` | enum | Yes | `BLOCK` → option dropped immediately; `MODIFY` → `modified_action_spec` is non-null; `DEFER` → retained but requires secondary auth |
| `policy_refs` | string[] | Yes | IDs of all policies evaluated; included in decision record |
| `modified_action_spec` | object | Conditional | Present only when `verdict = MODIFY`; replaces original `action_spec` |
| `requires_actor` | string | Conditional | Present only when `verdict = DEFER`; actor role required for secondary authorization |

---

## Evaluated Option

Produced by: Nexi — Option Evaluator (Step 7)
Consumed by: Nexi — Outcome Simulator, Decision Selector

```json
{
  "option_id": "uuid",
  "policy_verdict": "ALLOW | ALLOW_WITH_WARNINGS | MODIFY | DEFER",
  "scores": {
    "policy_score": 1.0,
    "outcome_score": 0.46,
    "risk_score": 0.55,
    "context_fit_score": 0.90
  },
  "composite_score": 0.68,
  "weight_config_version": "wc-v2.1",
  "simulation_required": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `policy_score` | float [0,1] | Yes | Derived from dry-run verdict: `ALLOW=1.0`, `ALLOW_WITH_WARNINGS=0.7`, `MODIFY=0.5` |
| `outcome_score` | float [0,1] | Yes | Pattern match against episodic history: `pattern.success_rate × pattern.confidence` |
| `risk_score` | float [0,1] | Yes | Composite: action reversibility + entity sensitivity + side effect count + actor type |
| `context_fit_score` | float [0,1] | Yes | Structural coverage ratio: option spec fields matched against intent constraints |
| `composite_score` | float [0,1] | Yes | Weighted sum using `weight_config_version` profile |
| `simulation_required` | bool | Yes | True if `risk_score > 0.6`, or `action.reversible = false`, or `actor.type = AGENT` |

**Composite score formula (EXECUTION intent_class defaults):**
```
composite = (policy_score × 0.25) + (outcome_score × 0.30) + (risk_score × 0.35) + (context_fit_score × 0.10)
```
Weight profiles are versioned and stored in xnch. The active profile version is embedded in `weight_config_version`.

---

## Decision Record

Produced by: Nexi — Decision Selector (Step 9)
Consumed by: xnch — `/verdict` (Step 10), Audit Logger

```json
{
  "decision_id": "uuid",
  "session_id": "uuid",
  "intent_ref": "uuid",
  "context_manifest_ref": "uuid",
  "system_state_version": "v3.2.1",
  "options_generated": 5,
  "options_blocked": 1,
  "options_evaluated": [
    {
      "option_id": "uuid",
      "scores": {
        "policy_score": 1.0,
        "outcome_score": 0.46,
        "risk_score": 0.55,
        "context_fit_score": 0.90
      },
      "composite_score": 0.68
    }
  ],
  "selected_option_id": "uuid",
  "selection_rationale": {
    "score_breakdown": {},
    "weight_config_version": "wc-v2.1"
  },
  "confidence": 0.13,
  "escalation_triggered": false,
  "generation_path": "MODEL | RULE_BASED"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `decision_id` | UUID | Yes | Used as idempotency key across resubmissions |
| `system_state_version` | string | Yes | xnch validates this matches current version at `/verdict`; mismatch = `STALE_SESSION` rejection |
| `options_generated` | int | Yes | Total options produced before any filtering |
| `options_blocked` | int | Yes | Count of options dropped by Policy Alignment Filter |
| `confidence` | float | Yes | `selected.composite_score - second_best.composite_score`; low margin is noted in audit record |
| `escalation_triggered` | bool | Yes | If true, `selected_option_id` is null and a hold record is written to xnch |
| `generation_path` | enum | Yes | `RULE_BASED` indicates model layer was unavailable; decision record is flagged accordingly |

---

## Verdict Response

Produced by: xnch — `/verdict` (Step 10)
Consumed by: Nexi — session completion, execution dispatch

```json
{
  "request_id": "uuid",
  "verdict": "ALLOW | BLOCK | MODIFY | DEFER",
  "verdict_reason": "string",
  "policy_refs": ["policy_id"],
  "modified_action": null,
  "execution_token": "eyJ...signed_jwt...",
  "token_ttl_ms": 30000,
  "audit_ref": "uuid"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `execution_token` | JWT | Conditional | Present only when `verdict = ALLOW` or `MODIFY`; RS256-signed by xnch private key |
| `token_ttl_ms` | int | Yes | Default 30000ms; execution-runner rejects expired tokens; Nexi must resubmit to `/verdict` |
| `audit_ref` | UUID | Yes | Reference to audit record written synchronously before this response was returned |
| `modified_action` | object | Conditional | Non-null when `verdict = MODIFY`; execution-runner receives this, not the original action spec |

---

## Execution Dispatch Payload

Produced by: Nexi — after verdict (Step 11)
Consumed by: execution-runner

```json
{
  "execution_ref": "uuid",
  "trace_id": "uuid",
  "decision_id": "uuid",
  "action_spec": {
    "type": "string",
    "target": "string",
    "params": {}
  },
  "execution_token": "eyJ...signed_jwt...",
  "token_ttl_ms": 30000
}
```

The execution-runner validates `execution_token` signature independently against xnch's public key. It does not trust Nexi's word that xnch approved the action. Token validation failure or TTL expiry causes rejection — Nexi receives a `TOKEN_EXPIRED` error and must resubmit to xnch `/verdict`.

---

## Execution Outcome

Produced by: execution-runner (Step 13)
Consumed by: xnch — `/execution/outcome`

```json
{
  "execution_ref": "uuid",
  "decision_id": "uuid",
  "execution_token_ref": "eyJ...",
  "outcome_status": "SUCCESS | PARTIAL | FAILURE | ROLLED_BACK",
  "observed_state_delta": {},
  "side_effects_observed": ["string"],
  "duration_ms": 38200,
  "anomalies": ["string"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `outcome_status` | enum | Yes | Written to episodic store; feeds `outcome_score` in future sessions |
| `observed_state_delta` | object | Yes | Structured diff of system state; compared against simulated projection if simulation ran |
| `side_effects_observed` | string[] | Yes | Actual side effects; compared against `estimated_side_effects` from option |
| `anomalies` | string[] | Yes | Unexpected conditions during execution; included in episode record for pattern extraction |

---

## Episode (Learning Record)

Produced by: xnch — after outcome callback (Step 14)
Consumed by: Pattern Extractor (6h schedule)

```json
{
  "episode_id": "uuid",
  "decision_id": "uuid",
  "intent_class": "EXECUTION",
  "action_type": "DEPLOY",
  "entity_class": "ML_MODEL",
  "actor_role": "OPERATOR",
  "outcome": "SUCCESS | PARTIAL | FAILURE",
  "prediction_delta": 0.54,
  "early_reextraction_flag": true,
  "context_snapshot": {},
  "created_at": "iso8601",
  "completed_at": "iso8601"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prediction_delta` | float | Yes | `abs(outcome_score_predicted - actual_success_rate)`; high delta (> 0.3) triggers early pattern extraction |
| `early_reextraction_flag` | bool | Yes | When true, Pattern Extractor runs immediately rather than waiting for 6h schedule |
| `context_snapshot` | object | Yes | System state at execution time; used to compute `context_signature` for pattern grouping |
| `completed_at` | iso8601 | Conditional | Null until outcome received; episodes with null `completed_at` after TTL are flagged stale |

---

## Pattern

Produced by: Pattern Extractor
Consumed by: Nexi — Option Evaluator (`outcome_score` computation)

```json
{
  "pattern_id": "uuid",
  "context_signature": "sha256:...",
  "intent_class": "EXECUTION",
  "action_type": "DEPLOY",
  "entity_class": "ML_MODEL",
  "success_rate": 0.75,
  "confidence": 0.61,
  "observation_count": 42,
  "avg_prediction_delta": 0.22,
  "extraction_run_id": "uuid",
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `context_signature` | sha256 | Yes | Hash of `(intent_class, action_type, entity_class, actor_role)` tuple; used as lookup key by Evaluator |
| `success_rate` | float [0,1] | Yes | `successful_episodes / total_episodes` for this context signature |
| `confidence` | float [0,1] | Yes | Bayesian-smoothed: `(success_count + 1) / (observation_count + 2)`; pattern not written until `observation_count ≥ 10` |
| `avg_prediction_delta` | float | Yes | Mean prediction error across all episodes in this group; high value indicates miscalibrated `outcome_score` weights |

---

## xnch Session Context

Produced by: xnch — `/session/init` (Step 2)
Consumed by: Nexi — session start

```json
{
  "session_id": "uuid",
  "trace_id": "uuid",
  "actor": {
    "id": "string",
    "role": "ADMIN | OPERATOR | VIEWER | AGENT",
    "capability_set": ["DEPLOY", "READ", "QUERY"]
  },
  "system_state_version": "v3.2.1",
  "policy_version": "v2.0.4",
  "idempotency_key": "uuid"
}
```

`capability_set` is resolved by xnch from internal governance store — it is never passed in by the caller. `system_state_version` must be echoed back by Nexi in every subsequent xnch call within this session. A mismatch causes `STALE_SESSION` rejection.

---

## Versioning Strategy

### Version Fields

Every core object that crosses a component boundary or is persisted to storage carries a version identifier. Objects that exist only within a single session in memory (e.g., intermediate scored options) are not versioned — they are ephemeral.

| Object | Version Field | Format | Scope |
|--------|--------------|--------|-------|
| Session Context | `system_state_version` | `v{major}.{minor}.{patch}` | System-wide; pins policy + state version for session |
| Session Context | `policy_version` | `v{major}.{minor}.{patch}` | Active policy set version at session init |
| Decision Record | `weight_config_version` | `wc-v{major}.{minor}` | Evaluation weight profile used for scoring |
| Episode | `schema_version` | `ep-v{major}` | Episode schema version; used for migration compatibility |
| Pattern | `schema_version` | `pt-v{major}` | Pattern schema version |
| Audit Ledger Entry | `schema_version` | `al-v{major}` | Ledger entry schema; immutable once written |

`system_state_version` is the primary version that flows through all inter-component calls. It is incremented by xnch when any of the following change: active policy set, weight configuration, or actor capability bindings. Incrementing `system_state_version` does not require restarting any process — in-flight sessions carry the old version and will be rejected at Step 10 if the new version was deployed after their Step 2.

### Backward Compatibility Rules

**Minor version increments** are backward-compatible. A component reading schema version `ep-v1.2` must be able to process objects written as `ep-v1.1` without error. New optional fields may be added. Existing fields may not be renamed, removed, or have their type changed.

**Major version increments** signal a breaking change. A component must explicitly support reading both `ep-v1.x` and `ep-v2.x` during a migration window, or old data must be migrated before the new version is activated.

**System state version** does not follow semver compatibility — it is not a data schema version. It is a monotonic sequence that gates session coherence. Any increment invalidates in-flight sessions regardless of magnitude.

### Schema Evolution Approach

New fields added to a schema must be:
1. Optional (not required) in the JSON schema definition
2. Given a documented default value that preserves existing behavior when absent
3. Added to the corresponding reference/schemas/ file before any code that writes or reads them is deployed

Fields are never removed from a schema in the same major version. If a field becomes obsolete, it is deprecated (documented as such) in the minor version and removed only in the next major version increment.

The Audit Ledger is exempt from evolution — ledger entries are write-once and immutable. The `schema_version` field in each entry ensures future readers can interpret historical records correctly even if the current schema has advanced.

### Migration Strategy for Stored Memory

Stored memory (Episode Store, Pattern Store, Context Store) may need migration when a major schema version increments.

**Approach: lazy migration with version tagging**

1. New schema version is deployed with a reader that handles both old and new versions
2. New writes use the new schema version
3. Reads check `schema_version` and apply a transform function if reading an old version
4. A background migration job runs during low-activity periods to rewrite old records to the new schema version
5. Once all records are at the new version, the old reader path is removed in the subsequent release

Episodes and Patterns that fail migration (due to schema incompatibility) are flagged in a migration error log and excluded from pattern extraction until resolved. They are not deleted — data loss is preferable to incorrect learning signal.

### Runtime Version Mismatch Handling

| Mismatch Type | Detection Point | Response |
|--------------|-----------------|---------|
| `system_state_version` skew (Nexi session vs current xnch) | Step 10 — `/verdict` | xnch rejects with `STALE_SESSION`; Nexi restarts session from Step 2 with same `idempotency_key` |
| `policy_version` change mid-session | Step 10 — `/verdict` | Same as above — `system_state_version` increments when policy changes, so this is caught by the same check |
| `weight_config_version` mismatch (Decision Record vs current) | Audit query time | Historical decisions retain the weight version used at decision time; no runtime rejection — mismatch is informational |
| Episode `schema_version` older than current reader | Pattern Extractor read | Lazy migration transform applied; if transform fails, episode excluded from this extraction run and flagged |
| Pattern `schema_version` older than current Nexi reader | Step 4 — manifest assembly | Lazy migration transform applied; if transform fails, pattern excluded from manifest and treated as absent |

**A version mismatch never causes silent data corruption.** The resolution is always one of: rejection with restart, exclusion with flag, or transform with error logging. No component silently reads a mismatched version and proceeds as if the data were current-schema.
