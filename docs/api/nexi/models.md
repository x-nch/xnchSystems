# Nexi wire models

Pydantic models in `nexi/models/` (plus request/response schemas in
`nexi/main.py`). Models appear on the wire either as **nexi HTTP request/response
bodies** or in the **payloads nexi sends to xnch / the execution runner**.

Enums are `StrEnum`; UUID fields are serialized as strings on the wire
(`model_dump(mode="json")`).

---

## Request / response schemas (defined in `nexi/main.py`)

### `SessionStartRequest` — `POST /session/start` body

| Field | Type | Default |
|-------|------|---------|
| `session_id` | UUID | required |
| `trace_id` | UUID | required |
| `actor` | `Actor` | required |
| `system_state_version` | str | required |
| `policy_version` | str | required |
| `raw_input` | str | required |
| `priority` | str | `"NORMAL"` |
| `idempotency_key` | UUID | required |

Validated into `SessionContext` (field-for-field identical).

### `SessionStartResponse` — `POST /session/start` body

| Field | Type | Default |
|-------|------|---------|
| `status` | str | required (`EXECUTING`/`CLARIFICATION_REQUIRED`/`ESCALATED`/`ERROR`) |
| `decision_id` | UUID \| None | `None` |
| `execution_ref` | UUID \| None | `None` |
| `estimated_completion_ms` | int \| None | `None` |
| `audit_ref` | UUID \| None | `None` |
| `clarification_required` | bool | `False` |
| `hold_id` | UUID \| None | `None` |
| `error` | str \| None | `None` |

---

## Enums

| Enum | Values |
|------|--------|
| `IntentClass` | `QUERY`, `DECISION`, `EXECUTION`, `ESCALATION` |
| `ActionType` | `READ_FILE`, `WRITE_FILE`, `DELETE_FILE`, `LIST`, `RUN_COMMAND`, `RUN_SCRIPT`, `DEPLOY`, `ROLLBACK`, `STAGE`, `MUTATE`, `BACKUP`, `RESTORE`, `PLAN`, `ANALYZE`, `ESCALATE`, `QUERY` |
| `Urgency` | `LOW`, `NORMAL`, `HIGH`, `CRITICAL` |
| `ActorRole` | `ADMIN`, `OPERATOR`, `VIEWER`, `AGENT` |
| `PolicyVerdict` | `ALLOW`, `ALLOW_WITH_WARNINGS`, `MODIFY`, `DEFER`, `BLOCK` |
| `GenerationPath` | `MODEL`, `RULE_BASED` |
| `OutcomeStatus` | `SUCCESS`, `PARTIAL`, `FAILURE`, `ROLLED_BACK` |

---

## Session / intent

### `Actor` (`nexi/models/session.py`)

| Field | Type |
|-------|------|
| `id` | str |
| `role` | `ActorRole` |
| `capability_set` | list[str] |

### `SessionContext` (`nexi/models/session.py`)

| Field | Type | Default |
|-------|------|---------|
| `session_id` | UUID | required |
| `trace_id` | UUID | required |
| `actor` | `Actor` | required |
| `system_state_version` | str | required |
| `policy_version` | str | required |
| `idempotency_key` | UUID | required |
| `raw_input` | str | required |
| `priority` | str | `"NORMAL"` |

### `Intent` (`nexi/models/intent.py`)

| Field | Type | Default |
|-------|------|---------|
| `intent_id` | UUID | `uuid4()` |
| `session_id` | UUID | required |
| `intent_class` | `IntentClass` | required |
| `action_type` | `ActionType` | required |
| `target_entity_id` | str | required |
| `target_entity_class` | str | required |
| `constraints_declared` | list[str] | `[]` |
| `urgency` | `Urgency` | `NORMAL` |
| `ambiguity_score` | float (0–1) | required |
| `raw_input_hash` | str | required (`sha256:` prefixed) |
| `raw_input` | str | `""` |
| `clarifications_needed` | list[str] | `[]` |

Internal to nexi — not in a nexi HTTP body, but its fields shape the `/memory/read` query.

---

## Options & policy

### `ActionSpec` (`nexi/models/options.py`)

| Field | Type | Default |
|-------|------|---------|
| `type` | str | required |
| `target` | str | required |
| `params` | dict[str, Any] | `{}` |

### `PlanOption` (`nexi/models/options.py`)

| Field | Type | Default |
|-------|------|---------|
| `option_id` | UUID | `uuid4()` |
| `action_type` | str | required |
| `action_spec` | `ActionSpec` | required |
| `stated_rationale` | str | required |
| `estimated_side_effects` | list[str] | `[]` |
| `reversible` | bool | required |
| `payload_hash` | str | required (`sha256:` of canonical spec JSON) |

Generated internally; sent to xnch `/policy/check` inside the dry-run `action` object.

### `PolicyDryRunResponse` (`nexi/models/options.py`) — from xnch `POST /policy/check`

| Field | Type | Default |
|-------|------|---------|
| `option_id` | UUID | required |
| `session_id` | UUID | required |
| `verdict` | `PolicyVerdict` | required |
| `policy_refs` | list[str] | required |
| `warnings` | list[str] | `[]` |
| `modified_action_spec` | `ActionSpec` \| None | `None` |
| `requires_actor` | str \| None | `None` |

### `Scores` (`nexi/models/options.py`)

| Field | Type |
|-------|------|
| `policy_score` | float (0–1) |
| `outcome_score` | float (0–1) |
| `risk_score` | float (0–1) |
| `context_fit_score` | float (0–1) |

### `EvaluatedOption` (`nexi/models/options.py`)

| Field | Type |
|-------|------|
| `option_id` | UUID |
| `policy_verdict` | `PolicyVerdict` |
| `scores` | `Scores` |
| `composite_score` | float (0–1) |
| `weight_config_version` | str |
| `simulation_required` | bool |

### `SelectionRationale` (`nexi/models/options.py`)

| Field | Type |
|-------|------|
| `score_breakdown` | dict[str, Any] |
| `weight_config_version` | str |

### `DecisionRecord` (`nexi/models/options.py`)

| Field | Type | Default |
|-------|------|---------|
| `decision_id` | UUID | `uuid4()` |
| `session_id` | UUID | required |
| `intent_ref` | UUID | required |
| `context_manifest_ref` | UUID | required |
| `system_state_version` | str | required |
| `options_generated` | int | required |
| `options_blocked` | int | required |
| `options_evaluated` | list[`EvaluatedOption`] | required |
| `selected_option_id` | UUID \| None | required |
| `selection_rationale` | `SelectionRationale` | required |
| `confidence` | float | required (top-score − runner-up score) |
| `escalation_triggered` | bool | `False` |
| `generation_path` | `GenerationPath` | `MODEL` |

Internal; its `decision_id` travels to xnch as `request_id` / `nexi_reasoning_ref`.

---

## Context manifest & memory (`nexi/models/outcomes.py`)

### `ContextManifest` — from xnch `POST /memory/read`

| Field | Type | Default |
|-------|------|---------|
| `manifest_id` | UUID | `uuid4()` |
| `session_id` | UUID | required |
| `system_state_version` | str | required |
| `pinned_at` | datetime (UTC) | now |
| `episodes` | list[`EpisodeRef`] | `[]` |
| `patterns` | list[`PatternRef`] | `[]` |
| `policies` | list[`PolicyRef`] | `[]` |

### `EpisodeRef`

| Field | Type |
|-------|------|
| `episode_id` | UUID |
| `action_type` | str |
| `entity_class` | str |
| `outcome` | str |
| `created_at` | datetime |
| `duration_ms` | int \| None |

### `PatternRef`

| Field | Type |
|-------|------|
| `pattern_id` | UUID |
| `context_signature` | str (`sha256:` of intent/action/entity/role tuple) |
| `success_rate` | float |
| `confidence` | float |
| `observation_count` | int |

### `PolicyRef`

| Field | Type |
|-------|------|
| `policy_id` | str |
| `rule_expression` | str |
| `enforcement_level` | str |

---

## Verdict, dispatch, outcome

### `VerdictResponse` (`nexi/models/outcomes.py`) — from xnch `POST /verdict`

| Field | Type | Default |
|-------|------|---------|
| `request_id` | UUID | required (= `decision_id`) |
| `verdict` | str | required |
| `verdict_reason` | str | required |
| `policy_refs` | list[str] | required |
| `modified_action` | dict[str, Any] \| None | `None` |
| `execution_token` | str \| None | `None` |
| `token_ttl_ms` | int | required |
| `audit_ref` | UUID | required |

### `ExecutionDispatchPayload` (`nexi/models/outcomes.py`) — sent to runner `POST /execute`

| Field | Type | Default |
|-------|------|---------|
| `execution_ref` | UUID | `uuid4()` |
| `trace_id` | UUID | required |
| `decision_id` | UUID | required |
| `action_spec` | dict[str, Any] | required (`{type, target, params}`) |
| `execution_token` | str | required |
| `token_ttl_ms` | int | required |

### `ExecutionOutcome` (`nexi/models/outcomes.py`) — posted to xnch `/execution/outcome` / runner

| Field | Type | Default |
|-------|------|---------|
| `execution_ref` | UUID | required |
| `decision_id` | UUID | required |
| `execution_token_ref` | str | required |
| `outcome_status` | `OutcomeStatus` | required |
| `observed_state_delta` | dict[str, Any] | `{}` |
| `side_effects_observed` | list[str] | `[]` |
| `duration_ms` | int | required |
| `anomalies` | list[str] | `[]` |

### `Episode` (`nexi/models/outcomes.py`) — full episodic record (internal / xnch-side)

| Field | Type | Default |
|-------|------|---------|
| `episode_id` | UUID | `uuid4()` |
| `decision_id` | UUID | required |
| `intent_class` | str | required |
| `action_type` | str | required |
| `entity_class` | str | required |
| `actor_role` | str | required |
| `outcome` | `OutcomeStatus` \| None | `None` |
| `prediction_delta` | float \| None | `None` |
| `early_reextraction_flag` | bool \| None | `None` |
| `context_snapshot` | dict[str, Any] | `{}` |
| `created_at` | datetime | now (UTC) |
| `completed_at` | datetime \| None | `None` |

---

## Compiled DAG (`nexi/models/dag.py`)

### `DAGNode`

| Field | Type |
|-------|------|
| `node_id` | str |
| `action_type` | str |
| `target` | str |
| `params` | dict[str, Any] |
| `depends_on` | list[str] |

### `CompiledDAG`

| Field | Type |
|-------|------|
| `nodes` | list[`DAGNode`] |
| `edges` | list[tuple[str, str]] |
| `entry_node` | str |

v0 always produces a single-node DAG (`compile_action_spec`); multi-step DAGs
are not yet produced.

---

## Wire flow summary

| nexi sends | HTTP | receives |
|------------|------|----------|
| `SessionStartRequest` | `POST /session/start` | `SessionStartResponse` |
| session + intent → query | `POST /memory/read` → xnch | `ContextManifest` |
| per-option action | `POST /policy/check` → xnch | `PolicyDryRunResponse` |
| decision + action spec | `POST /verdict` → xnch | `VerdictResponse` |
| `ExecutionDispatchPayload` | `POST /execute` → runner | accepted / `401 TOKEN_EXPIRED` |
| outcome (stub or real) | `POST /execution/outcome` → xnch | — |
| prediction delta | `POST /memory/write` → xnch | — |
