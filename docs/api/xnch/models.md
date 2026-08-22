# xnch Request / Response Models

Models are declared inline in the router modules (there is no central
`xnch/models/` package for HTTP bodies; the Pydantic models below live next to
their routes). Internal domain models (`SessionContext`, `ExecutionTokenClaims`,
`Actor`) are referenced where they shape the API.

---

## Session (`xnch/routes/session.py`)

### SessionInitRequest — `POST /session/init`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `auth_token` | str | — | HS256 JWT or `actor:<id>` dev ref |
| `raw_input` | str | — | free-form user input |
| `input_type` | str | `TEXT` | |
| `priority` | str | `NORMAL` | |
| `source_system` | str | `""` | |
| `trace_id` | str | uuid4 | if omitted, generated |
| `idempotency_key` | str | uuid4 | if omitted, generated; dedup key in Redis |

### ClarifyRequest — `POST /session/{session_id}/clarify`

| Field | Type |
|-------|------|
| `amended_input` | str |

### SessionContext (internal, forwarded to nexi)

Built in `session_init`; JSON shape sent to nexi `POST /session/start`:

```json
{
  "session_id": "uuid",
  "trace_id": "uuid",
  "actor": {"id": "operator", "role": "OPERATOR", "capability_set": ["DEPLOY","READ","QUERY"]},
  "system_state_version": "…",
  "policy_version": "…",
  "idempotency_key": "uuid",
  "raw_input": "…",
  "priority": "NORMAL"
}
```

---

## Memory (`xnch/routes/memory.py`)

### MemoryReadRequest — `POST /memory/read`

| Field | Type |
|-------|------|
| `session_id` | str |
| `actor_id` | str |
| `actor_role` | str |
| `query` | dict — keys below |

`query` keys: `intent_class` (str), `target_entity_class` (str),
`lookback_window_days` (int, default 30), `max_episodes` (int, default 20),
`max_patterns` (int, default 10).

### MemoryWriteRequest — `POST /memory/write`

| Field | Type |
|-------|------|
| `session_id` | str |
| `actor_id` | str |
| `write_type` | str — `EPISODE_PREDICTION_UPDATE` |
| `payload` | dict — `episode_id` (req), `prediction_delta`, `early_reextraction_flag` (bool) |

### Graph responses

| Model | Fields |
|-------|--------|
| `GraphEntityResponse` | `entity_id` str, `name` str, `type` str, `created_at` str\|null |
| `GraphRelationResponse` | `from_id`, `from_name?`, `to_id`, `to_name?`, `rel_type`, `confidence` float, `created_at?` |
| `GraphEntitiesPage` | `entities` list, `total` int, `limit` int, `offset` int |
| `GraphRelationsPage` | `relations` list, `total` int, `limit` int, `offset` int |
| `GraphSubgraphResponse` | `center_id` str, `depth` int, `entities` list, `relations` list |
| `GraphStatsResponse` | `entity_count` int, `relation_count` int, `types` dict[str,int] |

### Manifest response (memory/read)

```json
{
  "manifest_id": "uuid",
  "session_id": "…",
  "system_state_version": "…",
  "pinned_at": "ISO8601",
  "episodes": [
    {"episode_id": "…", "action_type": "…", "entity_class": "…",
     "outcome": "…", "duration_ms": 1234, "created_at": "ISO8601|null"}
  ],
  "patterns": [
    {"pattern_id": "…", "context_signature": "…", "success_rate": 0.8,
     "confidence": 0.9, "observation_count": 12}
  ],
  "policies": [
    {"policy_id": "…", "rule_expression": "EXECUTION|deploy|service|*",
     "enforcement_level": "ALLOW"}
  ]
}
```

---

## Policy (`xnch/routes/policy.py`)

### PolicyCheckRequest — `GET|POST /policy/check`

| Field | Type |
|-------|------|
| `session_id` | str |
| `system_state_version` | str |
| `actor_role` | str |
| `option_id` | str |
| `action` | dict — `intent_class`, `type`, `entity_class`, `actor_capabilities`, `spec`, `urgency`, `reversible` |

### Response

```json
{
  "option_id": "…",
  "session_id": "…",
  "verdict": "ALLOW",
  "policy_refs": [],
  "warnings": [],
  "modified_action_spec": null,
  "requires_actor": false
}
```

---

## Verdict (`xnch/routes/verdict.py`)

### VerdictRequest — `POST /verdict`

| Field | Type |
|-------|------|
| `request_id` | str |
| `actor` | dict — `{id: str, ...}` |
| `action` | dict — `intent_class`, `type`, `entity_class`, `payload`, `payload_hash` |
| `context` | dict — `session_id`, `system_state_version`, `outcome_score_predicted` |

### Response (ALLOW)

```json
{
  "request_id": "…",
  "verdict": "ALLOW",
  "verdict_reason": "allowed",
  "policy_refs": [],
  "modified_action": {},
  "execution_token": "<RS256 JWT>",
  "token_ttl_ms": 3600000,
  "audit_ref": "uuid"
}
```

### ExecutionTokenClaims (internal) & JWT payload

Signed RS256 by `TokenSigner.issue()` (`xnch/auth/token.py`). Claims:
`iss=xnch`, `sub=execution_token`, `jti`, `iat`, `exp`, `role`,
`session_id`, `decision_id`, `trace_id`, `actor_id`, `actor_role`,
`action_type`, `entity_class`, `policy_version`, `system_state_version`,
`token_ttl_ms`, `trust_level`.

TTL by actor trust level: SYSTEM 7d, OWNER 1d, TRUSTED_AGENT 1h,
EXTERNAL_AGENT 30m, UNTRUSTED 0.

---

## Execution (`xnch/routes/execution.py`)

### ExecutionOutcomeRequest — `POST /execution/outcome`

| Field | Type | Default |
|-------|------|---------|
| `execution_ref` | str | — |
| `decision_id` | str | — |
| `execution_token_ref` | str | `""` |
| `outcome_status` | str | — |
| `observed_state_delta` | dict | `{}` |
| `side_effects_observed` | list[str] | `[]` |
| `duration_ms` | int | 0 |
| `anomalies` | list[str] | `[]` |

**Response:** `{"status": "ok", "episode_id": "…"}`.

---

## Governance HITL (`xnch/routes/governance.py`)

### PipelineInvokeRequest — `POST /governance/pipeline/invoke`

| Field | Type | Default |
|-------|------|---------|
| `session_id` | str | — |
| `raw_input` | str | — |
| `trace_id` | str | uuid4 |
| `thread_id` | str | uuid4 |

### PipelineResumeRequest — `POST /governance/pipeline/resume`

| Field | Type | Notes |
|-------|------|-------|
| `thread_id` | str | required |
| `approved` | bool | optional; preferred is `decision` |
| `decision` | str | `"approve"` \| `"reject"` (preferred) |

Responses and the `/governance/pipeline/{thread_id}` status shape are
documented in [governance-hitl.md](governance-hitl.md).

---

## Nexi gateway (`xnch/routes/nexi_gateway.py`)

### ChatRequest — `POST /nexi/chat`, `/nexi/chat/stream`

| Field | Type | Default |
|-------|------|---------|
| `session_id` | str | — |
| `message` | str | — |
| `actor_role` | str | `operator` |

**Response (chat):** `{"response": "…", "model_used": "…", "session_id": "…"}`.

### MemoryRecallRequest — `POST /nexi/memory/recall`

| Field | Type | Default |
|-------|------|---------|
| `query` | str | — |
| `top_k` | int | 5 |

### Recall result item

```json
{
  "id": "…",
  "type": "episode",
  "timestamp": "…",
  "content": "…",
  "similarity": 0.71,
  "importance": 0.5,
  "relationships": [
    {"entity_a": "…", "entity_b": "…", "type": "…", "strength": 0.9}
  ]
}
```

---

## Chat completions (`xnch/routes/chat.py`)

### ChatCompletionRequest — `POST /v1/chat/completions`

| Field | Type |
|-------|------|
| `model` | str |
| `messages` | list[`ChatMessage`] — `{role: str, content: str}` |

### Response (OpenAI-compatible)

```json
{
  "id": "chatcmpl-<8hex>",
  "object": "chat.completion",
  "created": 1720000000,
  "model": "…",
  "choices": [
    {"index": 0, "message": {"role": "assistant", "content": "…"}, "finish_reason": "stop"}
  ]
}
```

---

## Voice (`xnch/routes/voice.py`)

### SpeakRequest — `POST /nexi/voice/speak`

| Field | Type |
|-------|------|
| `text` | str |
| `voice` | str \| null |

### transcribe response

Returned by `transcribe_audio(decoded)` — shape is subsystem-defined
(TODO: confirm exact schema from `xnch/voice/pipeline.py`).

### voice/chat response

`result.to_dict(include_audio=return_audio)` — shape is subsystem-defined
(TODO: confirm exact schema from `xnch/voice/pipeline.py`).

---

## MCP (`xnch_mcp/http_router.py`)

### ToolCallRequest — `POST /mcp/call`, `/mcp/call/batch`

| Field | Type | Default |
|-------|------|---------|
| `name` | str | — |
| `arguments` | dict | `{}` |

**Response (call):** `{"name": "…", "result": …}`.

---

## Actor (internal, shapes `/verdict`, `/session/init`)

`xnch/auth/governance.py::Actor` — `{id, role, capability_set}`. Bootstrapped
actors:

| actor_id | role | capability_set |
|----------|------|----------------|
| `admin` | ADMIN | `DEPLOY, READ, QUERY, ADMIN, SCHEMA_WRITE` |
| `operator` | OPERATOR | `DEPLOY, READ, QUERY` |
| `viewer` | VIEWER | `READ, QUERY` |
| `agent` | AGENT | `READ, QUERY, DEPLOY` |
