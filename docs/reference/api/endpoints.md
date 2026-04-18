# xnch + Nexi API Documentation

## OpenAPI 3.0 Specification

```yaml
openapi: 3.0.3
info:
  title: xnch + Nexi API
  version: 1.0.0
  description: |
    API for xnch intent-driven orchestration and Nexi decision intelligence system.
    xnch provides intent submission, plan compilation, simulation, execution, and memory capabilities.
    Nexi handles session management and decision-making for multi-step workflows.
```

---

## Table of Contents

1. [Intent APIs](#category-1-intent-apis)
2. [Plan APIs](#category-2-plan-apis)
3. [Simulation APIs](#category-3-simulation-apis)
4. [Execution APIs](#category-4-execution-apis)
5. [Memory & Policy APIs](#category-5-memory--policy-apis)
6. [Nexi APIs](#category-6-nexi-apis)
7. [Error Catalog](#error-catalog)

---

## Category 1: Intent APIs

### POST /v1/intent

Submit an intent for processing by the xnch orchestration engine.

**Description:** Submit a new intent to the xnch system. The intent is validated, processed through the decision engine, and queued for execution if policy-compliant.

**Request:**

```json
{
  "action": "DEPLOY",
  "target": "service:payment-gateway",
  "params": {
    "version": "v2.3.1",
    "environment": "staging",
    "replicas": 3
  },
  "actor_id": "user_8f3a2b1c",
  "actor_role": "developer",
  "system_state_version": "v1.45.0"
}
```

**Response (201 Created):**

```json
{
  "decision_id": "dec_7e9d4c3b2a1f",
  "intent": {
    "action": "DEPLOY",
    "target": "service:payment-gateway",
    "params": {"version": "v2.3.1", "environment": "staging", "replicas": 3},
    "actor_id": "user_8f3a2b1c",
    "actor_role": "developer"
  },
  "options_generated": 5,
  "options_blocked": 1,
  "selected_option_id": "opt_2a1b3c4d",
  "scores": {
    "policy_score": 0.95,
    "outcome_score": 0.88,
    "risk_score": 0.12,
    "context_fit_score": 0.91
  },
  "confidence": 0.87,
  "timestamp": "2026-04-18T10:30:00Z"
}
```

**Errors:** 400, 422, 429, 503

---

### POST /v1/verdict

Submit a post-execution verdict to record outcome and update learning models.

**Request:**

```json
{
  "decision_id": "dec_7e9d4c3b2a1f",
  "outcome": "SUCCESS",
  "actual_delta": {
    "deployed_version": "v2.3.1",
    "active_replicas": 3,
    "health_status": "healthy"
  }
}
```

**Response (200 OK):**

```json
{
  "verdict_id": "vrd_1a2b3c4d5e",
  "status": "recorded",
  "model_update_triggered": true,
  "improvement_score": 0.15
}
```

**Errors:** 400, 404, 409, 422

---

## Category 2: Plan APIs

### POST /v1/plan/compile

Compile multiple plan options for a given intent.

**Request:**

```json
{
  "intent": {
    "action": "EXECUTE",
    "target": "infra:migration",
    "params": {"source_env": "on-prem", "target_env": "cloud"},
    "actor_id": "user_ops_001",
    "actor_role": "operator"
  },
  "context": {
    "optimization_target": "cost",
    "constraints": ["max_downtime: 5m", "data_integrity: required"]
  }
}
```

**Response (200 OK):**

```json
{
  "compilation_id": "cmp_9f8e7d6c5b",
  "intent_hash": "a1b2c3d4e5f6",
  "options": [
    {
      "option_id": "opt_001",
      "description": "Phased migration with blue-green deployment",
      "action_spec": {
        "steps": [
          {"step": "backup", "timeout": "10m"},
          {"step": "migrate", "strategy": "incremental"},
          {"step": "verify", "checks": ["schema_integrity", "data_count"]}
        ]
      },
      "estimated_cost": 150.00,
      "estimated_duration": "45m"
    }
  ],
  "metadata": {"generation_time_ms": 234, "options_pruned": 2}
}
```

**Errors:** 400, 422, 503

---

## Category 3: Simulation APIs

### POST /v1/simulate

Simulate plan execution without actually performing actions.

**Request:**

```json
{
  "plan_option": {
    "option_id": "opt_001",
    "description": "Phased migration",
    "action_spec": {
      "steps": [
        {"step": "backup", "timeout": "10m"},
        {"step": "migrate", "strategy": "incremental"}
      ]
    },
    "estimated_cost": 150.00,
    "estimated_duration": "45m"
  },
  "system_state": {
    "services": {
      "payment-gateway": {"version": "v2.2.0", "replicas": 2, "status": "healthy"}
    }
  },
  "simulation_depth": "deep"
}
```

**Response (200 OK):**

```json
{
  "plan_id": "opt_001",
  "risk_score": 0.23,
  "side_effects": [
    "Service downtime during migration: ~2m expected",
    "Database connection pool will reset"
  ],
  "predicted_state_delta": {
    "services": {"payment-gateway": {"version": "v2.3.1", "replicas": 3}}
  },
  "diff": "services.payment-gateway: v2.2.0 → v2.3.1, replicas: 2 → 3"
}
```

**Errors:** 400, 404, 422, 503

---

## Category 4: Execution APIs

### POST /v1/execute

Execute a validated plan option.

**Request:**

```json
{
  "plan_option": {
    "option_id": "opt_2a1b3c4d",
    "description": "Deploy payment gateway v2.3.1",
    "action_spec": {
      "steps": [
        {"step": "pre_deploy_check"},
        {"step": "update_config"},
        {"step": "rolling_update", "max_surge": 1},
        {"step": "health_check"}
      ]
    },
    "estimated_cost": 45.00,
    "estimated_duration": "10m"
  },
  "decision_id": "dec_7e9d4c3b2a1f",
  "execution_config": {
    "timeout": "30m",
    "parallel_tasks": 2,
    "rollback_on_failure": true
  }
}
```

**Response (202 Accepted):**

```json
{
  "execution_id": "exe_5f4e3d2c1b",
  "status": "STARTED",
  "plan_option_id": "opt_2a1b3c4d",
  "started_at": "2026-04-18T10:35:00Z",
  "estimated_completion": "2026-04-18T10:45:00Z",
  "events_url": "wss://api.xnch.dev/v1/execution/exe_5f4e3d2c1b/events"
}
```

**Errors:** 400, 404, 409, 422, 503

---

### POST /v1/execution/outcome

Submit final execution outcome with detailed results.

**Request:**

```json
{
  "execution_id": "exe_5f4e3d2c1b",
  "status": "SUCCESS",
  "tasks_completed": 4,
  "tasks_failed": 0,
  "events": [
    {
      "timestamp": "2026-04-18T10:35:05Z",
      "event_type": "TASK_STARTED",
      "message": "Starting pre-deploy checks"
    },
    {
      "timestamp": "2026-04-18T10:37:00Z",
      "event_type": "EXECUTION_COMPLETED",
      "message": "All tasks completed successfully"
    }
  ],
  "execution_metrics": {
    "duration_ms": 115000,
    "cost_actual": 42.50
  }
}
```

**Response (200 OK):**

```json
{
  "outcome_id": "out_1a2b3c4d5e",
  "execution_id": "exe_5f4e3d2c1b",
  "status": "recorded",
  "stored_in_memory": true
}
```

**Errors:** 400, 404, 409, 422

---

## Category 5: Memory & Policy APIs

### GET /v1/memory/query

Query episode memory for historical patterns and learnings.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| intent_class | string | No | Filter by intent classification |
| action_type | string | No | Filter by action type |
| entity_class | string | No | Filter by entity class |
| outcome | string | No | Filter by outcome (SUCCESS/FAILURE) |
| limit | integer | No | Max results (default 50, max 200) |
| offset | integer | No | Pagination offset |

**Example:**

```bash
curl -X GET "https://api.xnch.dev/v1/memory/query?intent_class=DEPLOY&limit=10" \
  -H "Authorization: Bearer <token>"
```

**Response (200 OK):**

```json
{
  "episodes": [
    {
      "episode_id": "ep_8a7b6c5d4e",
      "intent_class": "DEPLOY",
      "action_type": "service",
      "entity_class": "payment-gateway",
      "outcome": "SUCCESS",
      "prediction_delta": 0.08,
      "timestamp": "2026-04-15T14:22:00Z"
    }
  ],
  "total_count": 156,
  "pagination": {"limit": 10, "offset": 0, "has_more": true}
}
```

**Errors:** 400, 422, 503

---

### GET /v1/policy/check

Check policy compliance for a proposed action.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| action | string | Yes | Action type |
| target | string | Yes | Target resource |
| actor_id | string | Yes | Actor attempting action |
| actor_role | string | Yes | Role of the actor |

**Response (200 OK):**

```json
{
  "allowed": true,
  "policy_version": "v2.1.0",
  "violations": []
}
```

**Response with Violations:**

```json
{
  "allowed": false,
  "policy_version": "v2.1.0",
  "violations": [
    {
      "policy_id": "pol_restrict_prod",
      "severity": "HIGH",
      "message": "Developer role not permitted to deploy to production"
    }
  ]
}
```

**Errors:** 400, 422, 503

---

## Category 6: Nexi APIs

### POST /v1/nexi/session

Start a new Nexi session for multi-step decision workflows.

**Request:**

```json
{
  "intent": {
    "action": "EXECUTE",
    "target": "infra:cloud-migration",
    "params": {"project": "Q2-migration"},
    "actor_id": "user_ops_042",
    "actor_role": "operator"
  },
  "session_type": "orchestration",
  "options_count": 5
}
```

**Response (201 Created):**

```json
{
  "session_id": "nxs_3c2b1a0d9e8",
  "intent": {
    "action": "EXECUTE",
    "target": "infra:cloud-migration"
  },
  "status": "PENDING",
  "created_at": "2026-04-18T10:00:00Z"
}
```

**Errors:** 400, 422, 429, 503

---

### GET /v1/nexi/decision/{decision_id}

Retrieve a specific decision from Nexi.

**Response (200 OK):**

```json
{
  "decision": {
    "decision_id": "ndc_9f8e7d6c5b",
    "options_generated": 5,
    "options_blocked": 2,
    "selected_option_id": "opt_phase2_batch",
    "scores": {
      "policy_score": 0.98,
      "outcome_score": 0.85,
      "risk_score": 0.18,
      "context_fit_score": 0.92
    },
    "confidence": 0.89,
    "timestamp": "2026-04-18T10:15:00Z"
  },
  "session_id": "nxs_3c2b1a0d9e8",
  "step_number": 2
}
```

**Errors:** 404, 403, 503

---

### GET /v1/nexi/session/{id}/options

Get available options for a Nexi session at current step.

**Response (200 OK):**

```json
{
  "session_id": "nxs_3c2b1a0d9e8",
  "current_step": 1,
  "total_steps": 4,
  "options": [
    {
      "option_id": "opt_full_migration",
      "description": "Full database migration in single batch",
      "prerequisites": ["backup_verified", "downtime_approved"],
      "estimated_duration": "4h"
    }
  ]
}
```

**Errors:** 404, 410, 503

---

### POST /v1/nexi/callback/outcome

Receive outcome callback from external system.

**Request:**

```json
{
  "decision_id": "ndc_9f8e7d6c5b",
  "outcome": "SUCCESS",
  "metadata": {
    "execution_id": "exe_5f4e3d2c1b",
    "duration_ms": 45000,
    "tasks_completed": 8,
    "tasks_failed": 0
  }
}
```

**Response (200 OK):**

```json
{
  "status": "processed",
  "next_step_triggered": true,
  "next_step": 3,
  "session_status": "IN_PROGRESS"
}
```

**Errors:** 400, 404, 409, 422

---

## Error Catalog

| Status | Error Code | Meaning | Resolution |
|--------|------------|---------|------------|
| 400 | `invalid_intent` | Intent action/target invalid | Check action enum and target format |
| 400 | `invalid_plan` | Plan cannot be compiled/executed | Validate action_spec structure |
| 400 | `invalid_outcome` | Malformed outcome data | Ensure tasks_completed + tasks_failed = total |
| 400 | `invalid_session_request` | Invalid Nexi session config | Check session_type and context |
| 400 | `invalid_query` | Invalid memory query | Validate filter parameters |
| 400 | `invalid_check` | Missing policy check params | Provide all required parameters |
| 400 | `invalid_callback` | Malformed callback payload | Verify decision_id and outcome |
| 404 | `decision_not_found` | Decision ID doesn't exist | Verify the decision_id from response |
| 404 | `session_not_found` | Session ID doesn't exist | Check session_id from creation response |
| 404 | `execution_not_found` | Execution ID doesn't exist | Use execution_id from execute response |
| 404 | `state_not_found` | System state version not found | Provide valid system_state_version |
| 409 | `execution_conflict` | Another execution in progress | Wait for completion or use different target |
| 409 | `duplicate_verdict` | Verdict already submitted | Each decision accepts one verdict |
| 409 | `duplicate_outcome` | Outcome already recorded | Each execution accepts one outcome |
| 409 | `duplicate_callback` | Callback already processed | Check for idempotency |
| 410 | `session_expired` | Session timed out | Create new session |
| 422 | `validation_error` | Schema validation failed | Check request body matches schema |
| 422 | `execution_config_invalid` | Invalid execution config | Validate timeout, parallel_tasks ranges |
| 422 | `simulation_timeout` | Simulation exceeded limit | Reduce simulation_depth or simplify plan |
| 429 | `rate_limit_exceeded` | Too many requests | Implement exponential backoff |
| 429 | `session_limit_exceeded` | Too many active sessions | Complete or cancel existing sessions |
| 503 | `service_unavailable` | xnch service down | Retry with backoff |
| 503 | `orchestration_engine_unavailable` | Intent processing unavailable | Retry later |
| 503 | `compiler_unavailable` | Plan compiler unavailable | Retry later |
| 503 | `simulator_error` | Simulation engine error | Retry or simplify plan |
| 503 | `executor_unavailable` | Execution engine unavailable | Retry later |
| 503 | `memory_unavailable` | Memory service unavailable | Retry later |
| 503 | `policy_service_unavailable` | Policy engine unavailable | Retry later |
| 503 | `nexi_unavailable` | Nexi service unavailable | Retry later |

---

## Schemas

### Intent

```json
{
  "action": "DEPLOY|QUERY|ANALYZE|EXECUTE",
  "target": "string",
  "params": {},
  "actor_id": "string",
  "actor_role": "string",
  "system_state_version": "string"
}
```

### PlanOption

```json
{
  "option_id": "string",
  "description": "string",
  "action_spec": {},
  "estimated_cost": "number",
  "estimated_duration": "string"
}
```

### DecisionRecord

```json
{
  "decision_id": "string",
  "intent": "Intent",
  "options_generated": "number",
  "options_blocked": "number",
  "selected_option_id": "string",
  "scores": {
    "policy_score": "number",
    "outcome_score": "number",
    "risk_score": "number",
    "context_fit_score": "number"
  },
  "confidence": "number",
  "timestamp": "datetime"
}
```

### Episode

```json
{
  "episode_id": "string",
  "intent_class": "string",
  "action_type": "string",
  "entity_class": "string",
  "outcome": "SUCCESS|FAILURE",
  "prediction_delta": "number",
  "timestamp": "datetime"
}
```

### ExecutionResult

```json
{
  "execution_id": "string",
  "status": "SUCCESS|FAILURE|PARTIAL",
  "tasks_completed": "number",
  "tasks_failed": "number",
  "events": []
}
```