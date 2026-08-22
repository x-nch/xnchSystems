# xnch HTTP API Reference

Base URL (gate7): `http://192.168.1.10:8001`

Auth header for routes that verify actor identity:
`Authorization: Bearer <hs256-jwt>` (or dev shorthand `Authorization: actor:<actor_id>`).

MCP routes read actor context from headers `X-Actor-Role`, `X-Trace-Id`, `X-Session-Id`.

---

## 1. App-level routes — `xnch/main.py`

### GET `/health`

Health + Redis liveness + state version.

| Field | Type | Notes |
|-------|------|-------|
| `status` | str | `ok` or `degraded` |
| `redis` | str | `ok` / `unavailable` |
| `state_version` | str | version from `get_state_version()` |
| `version` | str | `0.1.0` |

**Auth:** none.

### GET `/system/state`

| Field | Type |
|-------|------|
| `system_state_version` | str |
| `policy_version` | str |

**Auth:** none.

---

## 2. Session router — prefix `/session` — `xnch/routes/session.py`

### POST `/session/init`

Step 1–2: validate transport, dedup, rate-limit, resolve actor, then forward
`SessionContext` to nexi `POST /session/start`.

**Request body (`SessionInitRequest`):**

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `auth_token` | str | yes | — |
| `raw_input` | str | yes | — |
| `input_type` | str | no | `TEXT` |
| `priority` | str | no | `NORMAL` |
| `source_system` | str | no | `""` |
| `trace_id` | str | no | uuid4 |
| `idempotency_key` | str | no | uuid4 |

**Behavior / errors:**
- Returns cached `SessionContext` on idempotency-key dedup hit.
- `429` if `KVCache.check_rate_limit(actor)` fails (limit `XNCH_RATE_LIMIT_PER_MINUTE`).
- `401` if token invalid or actor unknown.
- `502` if nexi `/session/start` unreachable.

**Response:** the nexi `SessionStartResponse` body (proxied verbatim).

### POST `/session/{session_id}/clarify`

Actor submits clarified input for a WAITING session. Finds the session context
in Redis (`session:*` scan, v0 linear), replaces `raw_input`, re-forwards to
nexi `/session/start` with the same `session_id`.

**Request body (`ClarifyRequest`):**

| Field | Type | Required |
|-------|------|----------|
| `amended_input` | str | yes |

**Errors:** `404` session not found; `502` nexi unavailable.

**Response:** nexi response proxied verbatim.

---

## 3. Memory router — prefix `/memory` — `xnch/routes/memory.py`

### POST `/memory/read`

Step 4: return context manifest — episodes, patterns, policies scoped to the
context tuple. Consumed by nexi's `context_loader` via `XnchClient`.

**Request body (`MemoryReadRequest`):**

| Field | Type | Required |
|-------|------|----------|
| `session_id` | str | yes |
| `actor_id` | str | yes |
| `actor_role` | str | yes |
| `query` | dict | yes — see below |

`query` keys used:
`intent_class`, `target_entity_class`, `lookback_window_days` (default 30),
`max_episodes` (default 20), `max_patterns` (default 10).

**Response (`manifest`):**

| Field | Type | Notes |
|-------|------|-------|
| `manifest_id` | str | uuid4 |
| `session_id` | str | echoed |
| `system_state_version` | str | |
| `pinned_at` | str (ISO) | |
| `episodes` | list[dict] | `episode_id, action_type, entity_class, outcome, duration_ms, created_at` |
| `patterns` | list[dict] | `pattern_id, context_signature, success_rate, confidence, observation_count` |
| `policies` | list[dict] | `policy_id, rule_expression, enforcement_level` |

### POST `/memory/write`

Step 14: write prediction delta + early-extraction flag to an episode.

**Request body (`MemoryWriteRequest`):**

| Field | Type | Required |
|-------|------|----------|
| `session_id` | str | yes |
| `actor_id` | str | yes |
| `write_type` | str | yes — `EPISODE_PREDICTION_UPDATE` (only supported) |
| `payload` | dict | yes — `episode_id` (required), `prediction_delta`, `early_reextraction_flag` (bool, default false) |

**Behavior:**
- `403` if `get_capabilities(actor_role).can_write_memory` is false.
- `422` if `episode_id` missing.
- `400` for unknown `write_type`.
- If `early_reextraction_flag` true, triggers `PatternExtractor.run()` as a task.

**Response:** `{"status": "ok", "episode_id": ...}`.

### GET `/memory/graph/stats` → `GraphStatsResponse`

Kuzu L3 graph summary: `entity_count`, `relation_count`, `types` (dict[str,int]).

### GET `/memory/graph/entities` → `GraphEntitiesPage`

**Query params:** `type` (optional filter), `search` (substring on name),
`limit` (default 50, 1–500), `offset` (default 0).

**Response:** `{entities: [GraphEntityResponse], total, limit, offset}`.

### GET `/memory/graph/relations` → `GraphRelationsPage`

**Query params:** `limit` (default 100, 1–500), `offset` (default 0).

**Response:** `{relations: [GraphRelationResponse], total, limit, offset}`.

### GET `/memory/graph/subgraph` → `GraphSubgraphResponse`

**Query params:** `entity_id` (required), `depth` (default 1, 1–2).

**Response:** `{center_id, depth, entities: [...], relations: [...]}`.

### GET `/memory/graph/stream` — SSE

Stream of Kuzu graph mutations + stats. Event types: `stats`, `ready`,
`heartbeat`, `sync`. Media type `text/event-stream`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`. Each frame: `data: {json}\n\n`.

---

## 4. Policy router — prefix `/policy` — `xnch/routes/policy.py`

### GET/POST `/policy/check`

Contract 1: dry-run policy evaluation for one option. Same handler for both
methods.

**Request body (`PolicyCheckRequest`):**

| Field | Type | Required |
|-------|------|----------|
| `session_id` | str | yes |
| `system_state_version` | str | yes |
| `actor_role` | str | yes |
| `option_id` | str | yes |
| `action` | dict | yes — see below |

`action` keys read: `intent_class`, `type`, `entity_class`, `actor_capabilities`,
`spec`, `urgency` (default `NORMAL`), `reversible` (default true).

**Response:**

| Field | Type |
|-------|------|
| `option_id` | str |
| `session_id` | str |
| `verdict` | str (`ALLOW` / `BLOCK` / … per policy engine) |
| `policy_refs` | list |
| `warnings` | list |
| `modified_action_spec` | dict \| null |
| `requires_actor` | bool |

---

## 5. Verdict router — `xnch/routes/verdict.py` (no prefix)

### POST `/verdict`

Step 10: authoritative policy re-evaluation, Decision Ledger write, execution
token issuance.

**Request body (`VerdictRequest`):**

| Field | Type | Required |
|-------|------|----------|
| `request_id` | str | yes |
| `actor` | dict | yes — `{id, ...}` |
| `action` | dict | yes — `intent_class, type, entity_class, payload, payload_hash` |
| `context` | dict | yes — `session_id, system_state_version, outcome_score_predicted` |

**Behavior / errors:**
- `409 STALE_SESSION` if `context.system_state_version != current`.
- `401` if actor unknown.
- `BLOCK` verdict: writes ledger with 0 candidates, returns no token.
- `ALLOW`: issues RS256 execution token, writes ledger + episode (SQLite + PG),
  traces via Langfuse.

**Response (ALLOW):**

| Field | Type |
|-------|------|
| `request_id` | str |
| `verdict` | str |
| `verdict_reason` | str |
| `policy_refs` | list |
| `modified_action` | dict \| null |
| `execution_token` | str (JWT) |
| `token_ttl_ms` | int |
| `audit_ref` | str |

**Response (BLOCK):** same keys, `execution_token: null`, `token_ttl_ms: 0`.

---

## 6. Execution router — prefix `/execution` — `xnch/routes/execution.py`

### POST `/execution/execute`

Stub execution runner. Records a `SUCCESS` outcome (duration_ms=50) by calling
the same logic as `/execution/outcome`.

**Request body:** free-form dict; reads `execution_ref`, `decision_id`,
`execution_token`.

### POST `/execution/outcome`

Step 13: complete the decision episode, then fire-and-forget
`POST {nexi_base_url}/callback/outcome`.

**Request body (`ExecutionOutcomeRequest`):**

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

**Response:** `{"status": "ok", "episode_id": ...}`.

---

## 7. Governance router — prefix `/governance` — `xnch/routes/governance.py`

### GET `/governance/weights`

**Query param:** `intent_class` (required).

Returns active weight config, or defaults (`_default_weights`) when none
active. Weights sum to 1.0 per intent class.

**Response:** `{version, intent_class, weights}`.

Default weights (when not configured):

| Intent | weights |
|--------|---------|
| `EXECUTION` | policy 0.25 · outcome 0.30 · risk 0.35 · context_fit 0.10 |
| `QUERY` | 0.20 · 0.30 · 0.20 · 0.30 |
| `DECISION` | 0.25 · 0.35 · 0.25 · 0.15 |
| `ESCALATION` | 0.30 · 0.25 · 0.30 · 0.15 |

### POST `/governance/weights/propose`

**Request body (dict):** `intent_class`, `weights` (dict), optional
`episode_batch`, `proposed_by` (default `"api"`).

Inserts into `pending_weight_configs`. **Response:**
`{version: "wc-proposed-{hex8}", status: "pending"}`.

### POST `/governance/weights/approve`

**Query param:** `version` (required).

Validates sum ≈ 1.0 and each weight ≥ 0.05, deactivates prior config,
activates the proposed one, increments state version.

**Errors:** `404` unknown version; `422` invalid weights.

**Response:** `{version, status: "active"}`.

### POST `/governance/actors`

Upsert actor. **Request body (dict):** `actor_id`, `role`,
`capability_set` (list). Increments state version.

**Response:** `{status: "ok", actor_id}`.

### GET `/governance/policy-candidates`

Pending policy candidates from learning. **Response:** list of
`policy_candidates` rows where `status = 'PENDING'`, newest first.

### POST `/governance/pipeline/invoke`

LangGraph HITL invoke. See [governance-hitl.md](governance-hitl.md).

### POST `/governance/pipeline/resume`

LangGraph HITL resume. See [governance-hitl.md](governance-hitl.md).

### GET `/governance/pipeline/{thread_id}`

Thread status / pending interrupts. See [governance-hitl.md](governance-hitl.md).

---

## 8. Auth router — prefix `/auth` — `xnch/routes/auth.py`

### GET `/auth/public-key`

Serves the RS256 public key for verifying xnch-issued execution tokens.

**Response:** `{algorithm: "RS256", public_key_pem: "<pem>"}`.

---

## 9. Nexi gateway router — prefix `/nexi` — `xnch/routes/nexi_gateway.py`

### GET `/nexi/system-prompt`

Plain text. Builds the nexi system prompt from identity + capabilities + recent
graph entities. Cached in Redis under `nexi:system-prompt` (TTL 60s).

### GET `/nexi/capabilities`

`load_capabilities()` from nexi character config.

### GET `/nexi/tools`

Live tool inventory for the nexi actor (native + bridged).

**Response:** `{tools: [...], bridge: {active: bool, servers: [...]}}`.

### POST `/nexi/chat`

Single-turn chat through context assembly + LiteLLM.

**Request body (`ChatRequest`):**

| Field | Type | Default |
|-------|------|---------|
| `session_id` | str | — |
| `message` | str | — |
| `actor_role` | str | `operator` |

**Behavior:**
- `400` if input rejected by injection guard (`scan_input`).
- `502` if LiteLLM unavailable.
- Stores conversation episode in pgvector (dedup within 24h), invalidates
  system-prompt cache.

**Response:** `{response, model_used, session_id}`.

### POST `/nexi/chat/stream`

SSE variant. Same request body. Yields `data: {"content": ...}` then
`data: [DONE]`; `data: {"error": ...}` on LiteLLM failure.

### GET `/nexi/memory/surface`

Pending proactivity events from Redis. **Response:** list of event dicts.

### POST `/nexi/memory/recall`

Semantic memory recall.

**Request body (`MemoryRecallRequest`):** `query` (str), `top_k` (int, default 5).

**Response:** list of
`{id, type, timestamp, content, similarity, importance, relationships?}`.
`relationships` added when the matched entity exists in the Kuzu graph and has
PG relationships (`entity_a, entity_b, type, strength`).

---

## 10. Voice router — prefix `/nexi/voice` — `xnch/routes/voice.py`

All endpoints return `503` when `XNCH_VOICE_ENABLED=false`.

### POST `/nexi/voice/transcribe`

`multipart/form-data`: `audio` (file, required), `format` (form, default `wav`),
`sample_rate` (form, default 16000). Returns `transcribe_audio(decoded)` result.

### POST `/nexi/voice/speak`

**Request body (`SpeakRequest`):** `text` (str), `voice` (str\|null).
Returns `audio/wav` bytes.

### POST `/nexi/voice/speak/upload`

`multipart/form-data`: `text` (required). Returns `audio/wav` bytes.

### POST `/nexi/voice/chat`

Full voice loop. `multipart/form-data`: `audio` (file), `session_id`,
`actor_role` (default `operator`), `return_audio` (default true). Runs
`run_voice_chat`, returns `result.to_dict(include_audio=return_audio)`.

**Errors:** `400` on audio validation failure.

---

## 11. Chat router (OpenAI-compatible) — `xnch/routes/chat.py`

### POST `/v1/chat/completions`

OpenAI-compatible chat completions; creates a session and forwards to nexi
`/session/start`.

**Request body (`ChatCompletionRequest`):**

| Field | Type | Required |
|-------|------|----------|
| `model` | str | yes |
| `messages` | list[`ChatMessage`] | yes — `{role, content}`; last message content becomes raw_input |

**Auth:** `Authorization: Bearer <token>` (or `actor:<id>`) **required** —
`401` if missing/invalid/unknown actor. `400` if `messages` empty. `502` if
nexi unavailable.

**Response (OpenAI shape):** `{id: "chatcmpl-{session8}", object: "chat.completion",
created, model, choices: [{index:0, message: {role:"assistant", content}, finish_reason:"stop"}]}`.

---

## 12. Admin router — prefix `/admin` — `xnch/routes/admin.py`

### POST `/admin/consolidate`

Run graph extraction + episode decay with live stores.

**Response:** `{"status": "ok"}`.

### POST `/admin/reseed-identity`

Sync identity facts from `nexi_character.yaml` into pgvector; invalidates
system-prompt cache.

**Response:** `{status: "ok", added: int}`.

---

## 13. MCP router — prefix `/mcp` — `xnch_mcp/http_router.py` (external package)

Actor context from headers: `X-Actor-Role` (default `external`), `X-Trace-Id`,
`X-Session-Id`.

### GET `/mcp/tools`

`{actor, tools: [{name, description, tier}]}` filtered by actor role.

### GET `/mcp/tools/openai`

`{tools: [...]}` OpenAI function schemas.

### GET `/mcp/servers`

`{enabled: bool, servers: [...]}` — bridged MCP server status.

### POST `/mcp/call`

**Request body (`ToolCallRequest`):** `name`, `arguments` (dict).

**Errors:** `403` PermissionError, `400` ValueError, `500` other.

**Response:** `{name, result}`.

### POST `/mcp/call/batch`

Body: `list[ToolCallRequest]`. **Response:** `list[{name, result}]`.

---

## Error conventions

| Code | Meaning | Typical source |
|------|---------|----------------|
| 400 | Bad request / input rejected | injection guard, `write_type`, empty messages, audio validation |
| 401 | Invalid / unknown actor token | `/session/init`, `/verdict`, `/v1/chat/completions` |
| 403 | Missing capability / trust level | `/memory/write`, `/mcp/call` |
| 404 | Unknown resource | session not found, pending weights version, pipeline thread |
| 409 | Stale session version | `/verdict` |
| 422 | Validation | weights sum, missing fields, resume decision |
| 429 | Rate limit | `/session/init` |
| 500 | Internal / pipeline runtime failure | `/governance/pipeline/*` |
| 502 | Upstream unavailable (nexi / LiteLLM / LLM backend) | `/session/*`, `/nexi/chat`, `/v1/chat/completions` |
| 503 | Runtime not ready / subsystem disabled | pipeline HITL, voice |
