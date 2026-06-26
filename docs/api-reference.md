# XNCH/Nexi API Reference

**Version:** 0.1.0 | **Last updated:** 2026-06-27

---

## Table of Contents

1. [Authentication](#authentication)
   - [Token Types](#token-types)
   - [Actor Roles & Trust Levels](#actor-roles--trust-levels)
   - [Capability Matrix](#capability-matrix)
   - [Execution Token TTL](#execution-token-ttl)
   - [Quick Start](#quick-start)
2. [Error Catalog](#error-catalog)
3. [Health & System](#health--system)
   - [GET /health (xnch)](#get-health-xnch)
   - [GET /system/state](#get-systemstate)
   - [GET /health (Nexi)](#get-health-nexi)
4. [Authentication](#authentication-endpoints)
   - [GET /auth/public-key](#get-authpublic-key)
5. [Session](#session)
   - [POST /session/init](#post-sessioninit)
   - [POST /{session_id}/clarify](#post-session_idclarify)
   - [POST /session/start (Nexi)](#post-sessionstart-nexi)
   - [POST /callback/outcome (Nexi)](#post-callbackoutcome-nexi)
6. [Chat (Nexi Gateway)](#chat-nexi-gateway)
   - [POST /nexi/chat](#post-nexichat)
   - [POST /nexi/chat/stream](#post-nexichatstream)
   - [GET /nexi/system-prompt](#get-nexisystem-prompt)
   - [GET /nexi/memory/surface](#get-neximemorysurface)
   - [POST /nexi/memory/recall](#post-neximemoryrecall)
7. [Memory](#memory)
   - [POST /memory/read](#post-memoryread)
   - [POST /memory/write](#post-memorywrite)
8. [Policy & Verdict](#policy--verdict)
   - [GET /policy/check](#get-policycheck)
   - [POST /policy/check](#post-policycheck)
   - [POST /verdict](#post-verdict)
9. [Execution](#execution)
   - [POST /execution/outcome](#post-executionoutcome)
10. [Governance](#governance)
    - [GET /governance/weights](#get-governanceweights)
    - [POST /governance/weights/propose](#post-governanceweightspropose)
    - [POST /governance/weights/approve](#post-governanceweightsapprove)
    - [POST /governance/actors](#post-governanceactors)
    - [GET /governance/policy-candidates](#get-governancepolicy-candidates)
11. [Environment Variables](#environment-variables)
12. [Glossary](#glossary)

---

## Authentication

### Token Types

The API uses two token formats depending on the caller's context:

| Type | Algorithm | Usage |
|---|---|---|
| **Auth Token (HS256)** | HMAC-SHA256 | External callers authenticating to the xnch API. Verified by `TokenVerifier` using the shared secret (`XNCH_AUTH_SECRET`). |
| **Execution Token (RS256)** | RSA-SHA256 | Issued by the xnch verdict endpoint after policy approval. Proves authorization to the execution runner. Signed with the server's RSA keypair. |

Two formats are accepted for Auth Tokens:

```
# Plaintext actor reference (development only)
actor:<actor_id>

# HS256 JWT
Bearer <eyJhbGciOiJIUzI1NiIs...>
```

The HS256 JWT must contain a `sub` claim whose value is the `actor_id`. The shared secret used to verify the token is configured via `XNCH_AUTH_SECRET` (default: `dev-secret-change-in-production`).

### Actor Roles & Trust Levels

Trust is hierarchical on a 1–5 scale:

```
UNTRUSTED (1) < EXTERNAL_AGENT (2) < TRUSTED_AGENT (3) < OWNER (4) < SYSTEM (5)
```

| Actor Role | Trust Level | Description |
|---|---|---|
| `nexi` | SYSTEM (5) | The decision engine itself |
| `openclaw` | OWNER (4) | Primary human operator |
| `claude_code` | TRUSTED_AGENT (3) | Authorized AI coding agent |
| `opencode` | TRUSTED_AGENT (3) | Authorized AI coding agent |
| `perception_daemon` | TRUSTED_AGENT (3) | Perception pipeline service |
| `consolidation_job` | TRUSTED_AGENT (3) | Memory consolidation job |
| `external` | UNTRUSTED (1) | Unknown or unauthenticated callers |
| *(unknown)* | UNTRUSTED (1) | Unrecognized actor |

### Capability Matrix

| Capability | SYSTEM | OWNER | TRUSTED_AGENT | EXTERNAL_AGENT | UNTRUSTED |
|---|---|---|---|---|---|
| `can_write_memory` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `can_read_all_memory` | ✓ | ✓ | ✗ | ✗ | ✗ |
| `can_trigger_jobs` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `can_modify_policies` | ✓ | ✗ | ✗ | ✗ | ✗ |
| `can_access_perception` | ✓ | ✓ | ✗ | ✗ | ✗ |

### Execution Token TTL

| Trust Level | Max TTL |
|---|---|
| SYSTEM | 7 days (604,800,000 ms) |
| OWNER | 24 hours (86,400,000 ms) |
| TRUSTED_AGENT | 1 hour (3,600,000 ms) |
| EXTERNAL_AGENT | 30 minutes (1,800,000 ms) |
| UNTRUSTED | 0 (no token issued) |

### Trust Enforcement

The `@requires_trust(minimum)` decorator checks the `X-Actor-Role` header against the required trust level. Used on perception, consolidation, and governance endpoints. A `403 Forbidden` is returned if the role's trust level is insufficient.

### Key Pair

An RS256 2048-bit RSA key pair is auto-generated at `~/.xnch/keys/` on first boot. The public key is served at `GET /auth/public-key`.

### Governance Actors

Bootstrapped actors in the governance store:

| Actor ID | Role | Capabilities |
|---|---|---|
| `admin` | ADMIN | DEPLOY, READ, QUERY, ADMIN, SCHEMA_WRITE |
| `operator` | OPERATOR | DEPLOY, READ, QUERY |
| `viewer` | VIEWER | READ, QUERY |
| `agent` | AGENT | READ, QUERY, DEPLOY |

### Quick Start

**1. Generate an auth token (development):**

Use the plaintext format for local development:

```
actor:openclaw
```

**2. Call the health endpoint:**

```bash
# cURL
curl -X GET http://localhost:8001/health

# Expected response:
# {"status":"ok","redis":"ok","state_version":"abc123","version":"0.1.0"}
```

**3. Initiate a session:**

```bash
# cURL
curl -X POST http://localhost:8001/session/init \
  -H "Content-Type: application/json" \
  -d '{
    "auth_token": "actor:openclaw",
    "raw_input": "analyze the current memory usage",
    "input_type": "TEXT",
    "priority": "NORMAL"
  }'
```

```python
# Python
import requests

resp = requests.post(
    "http://localhost:8001/session/init",
    json={
        "auth_token": "actor:openclaw",
        "raw_input": "analyze the current memory usage",
        "input_type": "TEXT",
        "priority": "NORMAL"
    }
)
session = resp.json()
print(session)
```

---

## Error Catalog

### 400 Bad Request

Returned when the request is malformed or fails input validation.

| error_code | meaning | resolution |
|---|---|---|
| `injection_detected` | Input failed injection scan | Remove suspicious characters or restructure the input |
| `unknown_write_type` | `write_type` not recognized | Use a valid write type (e.g., `EPISODE_PREDICTION_UPDATE`) |
| `missing_episode_id` | Required field `episode_id` not provided | Include `episode_id` in the payload |
| `invalid_auth_token` | Auth token is malformed or uses wrong format | Use `actor:<id>` or `Bearer <jwt>` format |

### 401 Unauthorized

Returned when authentication fails or actor is unknown.

| error_code | meaning | resolution |
|---|---|---|
| `invalid_auth` | Token verification failed | Check `XNCH_AUTH_SECRET` or generate a valid HS256 JWT |
| `unknown_actor` | Actor ID not recognized by any trust mapping | Verify the actor ID or register it via governance |

### 403 Forbidden

Returned when the actor's trust level is insufficient for the endpoint.

| error_code | meaning | resolution |
|---|---|---|
| `insufficient_trust` | Actor lacks the required minimum trust level | Use an actor with a higher trust role |
| `insufficient_capabilities` | Actor lacks the required capability (e.g., `can_write_memory`) | Use SYSTEM, OWNER, or TRUSTED_AGENT role |
| `insufficient_permissions` | Actor role does not have the required governance permissions | Use `admin` actor for governance operations |

### 409 Conflict

Returned when system state is stale or a session version mismatch occurs.

| error_code | meaning | resolution |
|---|---|---|
| `STALE_SESSION` | System state version does not match current version | Re-initiate the session with the latest system state version |

### 422 Unprocessable Entity

Returned when request body is valid JSON but fails business validation.

| error_code | meaning | resolution |
|---|---|---|
| `empty_dag` | Compiled plan DAG has no nodes | Ensure the selected option produces actionable steps |
| `invalid_weights` | Weight config does not sum to 1.0 or contains values < 0.05 | Adjust weights to sum to 1.0 with each >= 0.05 |
| `weight_config_not_found` | No pending weight config found for given version | Check version or submit a new proposal |

### 429 Too Many Requests

Returned when rate limit is exceeded.

| error_code | meaning | resolution |
|---|---|---|
| `rate_limit_exceeded` | Actor has exceeded max requests per minute | Wait for the rate limit window to reset (default: 10/min) |

### 501 Not Implemented

| error_code | meaning | resolution |
|---|---|---|
| `not_implemented` | Endpoint is planned but not yet implemented | Check future release notes |

### 502 Bad Gateway

Returned when a downstream service is unavailable.

| error_code | meaning | resolution |
|---|---|---|
| `nexi_unavailable` | Nexi service refused the connection | Check that Nexi is running on port 8000 |
| `litellm_unavailable` | LiteLLM proxy refused the connection | Check that LiteLLM proxy is running |
| `context_manifest_unavailable` | Memory read returned no context | Verify PostgreSQL/pgvector and Redis connectivity |

### 503 Service Unavailable

| error_code | meaning | resolution |
|---|---|---|
| `context_manifest_unavailable` | Memory context could not be assembled | Check database connectivity |

---

## Health & System

### GET /health (xnch)

**Server:** xnch (port 8001)
**Trust required:** None
**Description:** Health check for the xnch control plane. Reports Redis connectivity status and current system state version.

**Response:**

```json
{
  "status": "ok",
  "redis": "ok",
  "state_version": "v_abc123def",
  "version": "0.1.0"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` if all subsystems are healthy, `"degraded"` if non-critical failures exist |
| `redis` | string | `"ok"` or `"unavailable"` |
| `state_version` | string | Current system state version identifier |
| `version` | string | API version (`0.1.0`) |

**Errors:** None (always returns 200).

```bash
# cURL
curl -X GET http://localhost:8001/health
```

```python
# Python
import requests

resp = requests.get("http://localhost:8001/health")
resp.raise_for_status()
print(resp.json())
```

---

### GET /system/state

**Server:** xnch (port 8001)
**Trust required:** None
**Description:** Returns the current system state version and policy version. Used by Nexi to verify state consistency before proceeding with a session.

**Response:**

```json
{
  "system_state_version": "v_abc123def",
  "policy_version": "p_789ghi"
}
```

| Field | Type | Description |
|---|---|---|
| `system_state_version` | string | Monotonic version ID incremented on weight config approvals |
| `policy_version` | string | Current active policy version |

**Errors:** None.

```bash
# cURL
curl -X GET http://localhost:8001/system/state
```

```python
# Python
import requests

resp = requests.get("http://localhost:8001/system/state")
print(resp.json())
```

---

### GET /health (Nexi)

**Server:** Nexi (port 8000)
**Trust required:** None
**Description:** Health check for the Nexi decision engine.

**Response:**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` if Nexi is operational |
| `version` | string | Nexi version (`0.1.0`) |

**Errors:** None.

```bash
# cURL
curl -X GET http://localhost:8000/health
```

---

## Authentication Endpoints

### GET /auth/public-key

**Server:** xnch (port 8001)
**Trust required:** None
**Description:** Serves the RS256 public key in PEM format. Used by external services to validate execution tokens issued by the verdict endpoint. The key pair is auto-generated at `~/.xnch/keys/` on first boot.

**Response:**

```json
{
  "algorithm": "RS256",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----"
}
```

| Field | Type | Description |
|---|---|---|
| `algorithm` | string | Always `"RS256"` |
| `public_key_pem` | string | PEM-encoded 2048-bit RSA public key |

**Errors:** None.

```bash
# cURL
curl -X GET http://localhost:8001/auth/public-key
```

```python
# Python
import requests

resp = requests.get("http://localhost:8001/auth/public-key")
key_data = resp.json()
public_key = key_data["public_key pem"]
# Use with PyJWT or cryptography library to verify tokens
```

---

## Session

### POST /session/init

**Server:** xnch (port 8001)
**Trust required:** None (auth token is validated in the request body)
**Description:** Two-phase session initiation — the entry point for all external requests.

**Phase 1 (xnch):** Validates the auth token, checks idempotency via KV cache dedup, enforces rate limiting (default 10 req/min per actor), resolves the actor from the governance store, creates a session context, and caches it in Redis.

**Phase 2 (Nexi):** Forwards the validated request to Nexi `POST /session/start`, which runs the full decision pipeline.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `auth_token` | string | **yes** | — | Auth token: `actor:<id>` or `Bearer <hs256-jwt>` |
| `raw_input` | string | **yes** | — | The natural-language or structured input |
| `input_type` | string | no | `"TEXT"` | Type of input (`TEXT`, `COMMAND`, `QUERY`, etc.) |
| `priority` | string | no | `"NORMAL"` | Priority level (`NORMAL`, `HIGH`, `LOW`) |
| `source_system` | string | no | `""` | Identifier for the originating system |
| `trace_id` | string \| null | no | `null` | Client-provided trace ID for distributed tracing |
| `idempotency_key` | string \| null | no | `null` | Client-provided idempotency key for deduplication |

**Example request:**

```json
{
  "auth_token": "actor:openclaw",
  "raw_input": "schedule memory consolidation for all high-importance episodes",
  "input_type": "COMMAND",
  "priority": "HIGH",
  "idempotency_key": "client-abc-123"
}
```

**Response:** Passthrough from Nexi `SessionStartResponse`:

```json
{
  "status": "EXECUTING",
  "decision_id": "dec_abc123",
  "execution_ref": "exec_def456",
  "estimated_completion_ms": 4500,
  "audit_ref": "aud_789ghi",
  "clarification_required": false,
  "hold_id": null,
  "error": null
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | One of `EXECUTING`, `CLARIFICATION_REQUIRED`, `ESCALATED`, `ERROR` |
| `decision_id` | UUID \| null | Unique decision identifier |
| `execution_ref` | UUID \| null | Reference for execution tracking |
| `estimated_completion_ms` | int \| null | Estimated pipeline completion time in milliseconds |
| `audit_ref` | UUID \| null | Audit trail reference |
| `clarification_required` | bool | Whether the system needs more information |
| `hold_id` | UUID \| null | Hold identifier if clarification is needed |
| `error` | string \| null | Error message if status is `ERROR` |

**Errors:** `401` invalid auth / unknown actor, `429` rate limit exceeded, `502` Nexi unavailable.

```bash
# cURL
curl -X POST http://localhost:8001/session/init \
  -H "Content-Type: application/json" \
  -d '{
    "auth_token": "actor:openclaw",
    "raw_input": "schedule memory consolidation for all high-importance episodes",
    "input_type": "COMMAND",
    "priority": "HIGH",
    "idempotency_key": "client-abc-123"
  }'
```

```python
# Python
import requests

resp = requests.post(
    "http://localhost:8001/session/init",
    json={
        "auth_token": "actor:openclaw",
        "raw_input": "analyze anomaly patterns in recent perception data",
        "input_type": "TEXT",
        "priority": "NORMAL",
    }
)
resp.raise_for_status()
result = resp.json()
print(f"Session status: {result['status']}")
print(f"Decision ID: {result['decision_id']}")
```

---

### POST /{session_id}/clarify

**Server:** xnch (port 8001)
**Trust required:** None
**Description:** Submits clarified input for a session that is in `WAITING` status (when the initial response returned `clarification_required: true`).

**Note:** Not yet implemented in v0.

**Errors:** `501` Not Implemented.

```bash
# cURL
curl -X POST http://localhost:8001/ses_abc123/clarify \
  -H "Content-Type: application/json" \
  -d '{
    "clarified_input": "yes, include latent pattern analysis",
    "hold_id": "hold_def456"
  }'
```

---

### POST /session/start (Nexi)

**Server:** Nexi (port 8000)
**Trust required:** Called internally by xnch — not exposed externally
**Description:** Entry point called by xnch after actor resolution (Step 2 → Step 3). Runs the full decision pipeline:

1. Intent interpretation
2. Context manifest assembly (via xnch `POST /memory/read`)
3. Weight config fetch
4. Option generation via LLM
5. Policy filter (via xnch `POST /policy/check`)
6. Weighted scoring
7. Outcome simulation and rescore
8. Best option selection
9. Plan compilation (DAG construction)
10. Verdict (via xnch `POST /verdict`)
11. Execution dispatch
12. Response assembly

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | UUID | **yes** | Session identifier from xnch |
| `trace_id` | UUID | **yes** | Distributed tracing identifier |
| `actor` | dict[str, Any] | **yes** | Resolved actor object (id, role, trust level, capabilities) |
| `system_state_version` | string | **yes** | Current system state version |
| `policy_version` | string | **yes** | Current policy version |
| `raw_input` | string | **yes** | Original input from the user |
| `priority` | string | no | `"NORMAL"` (default), `"HIGH"`, or `"LOW"` |
| `idempotency_key` | UUID | **yes** | Idempotency key for deduplication |

**Response:**

```json
{
  "status": "EXECUTING",
  "decision_id": "dec_abc123",
  "execution_ref": "exec_def456",
  "estimated_completion_ms": 4500,
  "audit_ref": "aud_789ghi",
  "clarification_required": false,
  "hold_id": null,
  "error": null
}
```

**Errors:** `503` context manifest unavailable, `409` STALE_SESSION, `422` empty DAG.

---

### POST /callback/outcome (Nexi)

**Server:** Nexi (port 8000)
**Trust required:** Called internally by xnch — not exposed externally
**Description:** Called by xnch after writing an execution outcome (Step 14). Computes the prediction delta between the expected and actual outcome. If the delta exceeds 0.3, triggers early re-extraction of patterns. Writes the prediction update back to xnch memory.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `execution_ref` | string | **yes** | Execution reference identifier |
| `decision_id` | string | **yes** | Decision identifier |
| `episode_id` | string \| null | no | Episode identifier |
| `outcome_status` | string | **yes** | `"SUCCESS"`, `"FAILURE"`, `"PARTIAL"`, or custom |
| `trace_id` | string | **yes** | Distributed tracing identifier |

**Response:**

```json
{
  "status": "ok"
}
```

**Errors:** None (errors are logged but not returned to the caller).

---

## Chat (Nexi Gateway)

### POST /nexi/chat

**Server:** xnch (port 8001)
**Trust required:** OWNER+ (semantic — the `nexi_gateway` router is gated by actor resolution)
**Description:** Main chat/completion endpoint. Runs the full inference pipeline:

1. **Injection scan** — validates input against injection patterns
2. **Context assembly** — gathers working memory, episodic memory (`pg_episodic`), graph store, relationship store, sensory buffer, and proactivity engine state
3. **Request classification** — determines intent and entity targets
4. **LiteLLM call** — delegates to the configured LLM via LiteLLM proxy
5. **Working memory write** — stores the interaction in short-term memory
6. **Episodic store** — persists to `pg_episodic` if the memory guard allows
7. **System prompt cache invalidation** — busts the Redis cache for next request

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | string | **yes** | — | Active session identifier |
| `message` | string | **yes** | — | The message to process |
| `actor_role` | string | no | `"openclaw"` | Actor role for context and memory scoping |

**Response:**

```json
{
  "response": "Based on the current memory usage patterns, I've identified 3 episodes with anomalous allocation...",
  "model_used": "gemma4-local",
  "session_id": "ses_abc123"
}
```

| Field | Type | Description |
|---|---|---|
| `response` | string | The model-generated response text |
| `model_used` | string | The model identifier used for inference |
| `session_id` | string | Echoed session identifier |

**Errors:** `400` injection detected, `502` LiteLLM unavailable.

```bash
# cURL
curl -X POST http://localhost:8001/nexi/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ses_abc123",
    "message": "Summarize recent anomaly patterns",
    "actor_role": "openclaw"
  }'
```

```python
# Python
import requests

resp = requests.post(
    "http://localhost:8001/nexi/chat",
    json={
        "session_id": "ses_abc123",
        "message": "Summarize recent anomaly patterns",
        "actor_role": "openclaw"
    }
)
resp.raise_for_status()
result = resp.json()
print(f"Model: {result['model_used']}")
print(f"Response: {result['response']}")
```

---

### POST /nexi/chat/stream

**Server:** xnch (port 8001)
**Trust required:** OWNER+
**Description:** Same as `/nexi/chat` but returns a Server-Sent Events (SSE) stream. Each chunk is a JSON object with a `content` field. The stream terminates with `data: [DONE]\n\n`.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | string | **yes** | — | Active session identifier |
| `message` | string | **yes** | — | The message to process |
| `actor_role` | string | no | `"openclaw"` | Actor role for context and memory scoping |

**Response:** `text/event-stream`

```
data: {"content": "Based on"}

data: {"content": " the current"}

data: {"content": " memory patterns..."}

data: [DONE]
```

**Errors:** `400` injection detected, SSE error events on LiteLLM failure.

```bash
# cURL
curl -N -X POST http://localhost:8001/nexi/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ses_abc123",
    "message": "Summarize recent anomaly patterns"
  }'
```

```python
# Python
import requests
import json

resp = requests.post(
    "http://localhost:8001/nexi/chat/stream",
    json={
        "session_id": "ses_abc123",
        "message": "Summarize recent anomaly patterns",
    },
    stream=True
)
for line in resp.iter_lines():
    if line:
        line = line.decode("utf-8")
        if line.startswith("data: "):
            payload = line[6:]
            if payload == "[DONE]":
                break
            data = json.loads(payload)
            print(data["content"], end="", flush=True)
```

---

### GET /nexi/system-prompt

**Server:** xnch (port 8001)
**Trust required:** OWNER+
**Description:** Returns the assembled system prompt used for LLM inference. Results are cached in Redis for 60 seconds (key: `nexi:system-prompt`). On cache miss: fetches recent entities from agentmemory, calls `build_system_prompt()`, and caches the result.

**Response:** `text/plain`

```
You are Nexi, an AI orchestration engine running on a split-node architecture.
Your role is to interpret intent, assemble context, evaluate options, and dispatch
execution with full policy compliance...

Current system state: v_abc123def
Active actors: [openclaw, claude_code, nexi]
...
```

**Errors:** None.

```bash
# cURL
curl -X GET http://localhost:8001/nexi/system-prompt
```

---

### GET /nexi/memory/surface

**Server:** xnch (port 8001)
**Trust required:** OWNER+
**Description:** Returns pending proactivity events from the ProactivityEngine — surfaced memories, intentions, and scheduled actions that the system deems contextually relevant.

**Response:** `list[dict]`

```json
[
  {
    "id": "pro_001",
    "type": "memory_surfacing",
    "priority": 0.85,
    "content": "Episode ep_abc123 completed with anomalous outcome delta 0.4",
    "intent": "REVIEW",
    "created_at": "2026-06-27T04:00:00Z",
    "expires_at": "2026-06-27T05:00:00Z"
  },
  {
    "id": "pro_002",
    "type": "intention",
    "priority": 0.65,
    "content": "Scheduled consolidation due in 15 minutes",
    "intent": "CONSOLIDATE",
    "created_at": "2026-06-27T04:30:00Z",
    "expires_at": "2026-06-27T04:45:00Z"
  }
]
```

**Errors:** None.

```bash
# cURL
curl -X GET http://localhost:8001/nexi/memory/surface
```

---

### POST /nexi/memory/recall

**Server:** xnch (port 8001)
**Trust required:** OWNER+
**Description:** Semantic memory recall from the `pg_episodic` store. Retrieves episodes similar to the query text using vector similarity search (pgvector). Includes relationship data from the graph store.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | **yes** | — | Natural-language query for semantic search |
| `top_k` | int | no | `5` | Number of top results to return |

**Response:** `list[dict]`

```json
[
  {
    "id": "ep_abc123",
    "type": "episode",
    "timestamp": "2026-06-27T03:00:00Z",
    "content": "Actor openclaw requested memory consolidation. Decision: ALLOW. Outcome: SUCCESS.",
    "similarity": 0.89,
    "importance": 0.75,
    "relationships": [
      {
        "entity_a": "openclaw",
        "entity_b": "consolidation_job",
        "type": "TRIGGERED",
        "strength": 0.9
      }
    ]
  }
]
```

**Errors:** None.

```bash
# cURL
curl -X POST http://localhost:8001/nexi/memory/recall \
  -H "Content-Type: application/json" \
  -d '{
    "query": "memory consolidation requests",
    "top_k": 5
  }'
```

```python
# Python
import requests

resp = requests.post(
    "http://localhost:8001/nexi/memory/recall",
    json={"query": "memory consolidation requests", "top_k": 5}
)
results = resp.json()
for r in results:
    print(f"[{r['similarity']:.2f}] {r['content'][:80]}...")
```

---

## Memory

### POST /memory/read

**Server:** xnch (port 8001)
**Trust required:** Called by Nexi internally
**Description:** Step 4 of the decision pipeline. Returns a context manifest containing episodes, patterns, and policies that match the given intent class, entity class, and actor role within the specified lookback window.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | **yes** | Session identifier |
| `actor_id` | string | **yes** | Resolved actor ID |
| `actor_role` | string | **yes** | Resolved actor role |
| `query.intent_class` | string | **yes** | Intent classification (e.g., `EXECUTION`, `QUERY`, `DECISION`, `ESCALATION`) |
| `query.target_entity_id` | string | **yes** | Target entity identifier |
| `query.target_entity_class` | string | **yes** | Target entity class |
| `query.lookback_window_days` | int | no | `30` | Days of history to search |
| `query.max_episodes` | int | no | `20` | Maximum episodes to return |
| `query.max_patterns` | int | no | `10` | Maximum patterns to return |

**Response:**

```json
{
  "manifest_id": "mft_abc123",
  "session_id": "ses_abc123",
  "system_state_version": "v_abc123def",
  "pinned_at": "2026-06-27T04:00:00Z",
  "episodes": [
    {
      "episode_id": "ep_001",
      "action_type": "MEMORY_READ",
      "entity_class": "actor",
      "outcome": "SUCCESS",
      "created_at": "2026-06-27T03:00:00Z"
    }
  ],
  "patterns": [
    {
      "pattern_id": "pat_001",
      "context_signature": "intent=QUERY,entity=memory",
      "success_rate": 0.95,
      "confidence": 0.85,
      "observation_count": 42
    }
  ],
  "policies": [
    {
      "policy_id": "pol_001",
      "rule_expression": "actor.trust >= TRUSTED_AGENT AND action.type == MEMORY_WRITE",
      "enforcement_level": "HARD"
    }
  ]
}
```

**Errors:** `503` context manifest unavailable.

---

### POST /memory/write

**Server:** xnch (port 8001)
**Trust required:** Actor must have `can_write_memory` capability (checked via `get_capabilities(actor_role)`). SYSTEM, OWNER, and TRUSTED_AGENT roles pass.
**Description:** Step 14 of the decision pipeline. Writes a prediction delta and optional early re-extraction flag to an episode. If `early_reextraction_flag` is `true`, triggers async pattern extraction.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | **yes** | Session identifier |
| `actor_id` | string | **yes** | Actor ID |
| `write_type` | string | **yes** | Must be `"EPISODE_PREDICTION_UPDATE"` |
| `payload.episode_id` | string | **yes** | Target episode identifier |
| `payload.prediction_delta` | float | **yes** | Absolute difference between predicted and actual outcome (0.0–1.0) |
| `payload.early_reextraction_flag` | bool | no | `false` | Whether to trigger async pattern re-extraction |

**Example request:**

```json
{
  "session_id": "ses_abc123",
  "actor_id": "nexi",
  "write_type": "EPISODE_PREDICTION_UPDATE",
  "payload": {
    "episode_id": "ep_001",
    "prediction_delta": 0.42,
    "early_reextraction_flag": true
  }
}
```

**Response:**

```json
{
  "status": "ok",
  "episode_id": "ep_001"
}
```

**Errors:** `403` insufficient capabilities, `422` missing `episode_id`, `400` unknown `write_type`.

---

## Policy & Verdict

### GET /policy/check

**Server:** xnch (port 8001)
**Trust required:** Called by Nexi internally
**Description:** Alias for the policy check endpoint using GET. Same behavior as POST.

See [POST /policy/check](#post-policycheck) for request and response details.

---

### POST /policy/check

**Server:** xnch (port 8001)
**Trust required:** Called by Nexi internally
**Description:** Contract 1 (Pipeline Step 5): Dry-run policy evaluation for a single generated option. Returns the verdict, matching policy references, warnings, a modified action spec (if the policy suggests modifications), and the required actor if escalation is needed. Does not issue execution tokens — this is a non-authoritative pre-check.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | string | **yes** | — | Session identifier |
| `system_state_version` | string | **yes** | — | Current system state version |
| `actor_role` | string | **yes** | — | Role of the actor requesting the action |
| `option_id` | string | **yes** | — | Identifier of the option being evaluated |
| `action.type` | string | **yes** | — | Action type (e.g., `MEMORY_WRITE`, `EXECUTE`, `QUERY`) |
| `action.target` | string | **yes** | — | Action target identifier |
| `action.spec` | dict | **yes** | — | Action-specific parameters |
| `action.intent_class` | string | **yes** | — | Intent classification |
| `action.entity_class` | string | **yes** | — | Entity class |
| `action.actor_capabilities` | list[str] | **yes** | — | Capabilities the actor claims |
| `action.urgency` | string | no | `"NORMAL"` | `"LOW"`, `"NORMAL"`, or `"HIGH"` |
| `action.reversible` | bool | no | `true` | Whether the action can be reversed |
| `action.payload_hash` | string | **yes** | — | Hash of the action payload for integrity |

**Example request:**

```json
{
  "session_id": "ses_abc123",
  "system_state_version": "v_abc123def",
  "actor_role": "nexi",
  "option_id": "opt_001",
  "action": {
    "type": "MEMORY_WRITE",
    "target": "ep_001",
    "spec": {
      "write_type": "EPISODE_PREDICTION_UPDATE",
      "prediction_delta": 0.42
    },
    "intent_class": "EXECUTION",
    "entity_class": "episode",
    "actor_capabilities": ["can_write_memory"],
    "urgency": "NORMAL",
    "reversible": false,
    "payload_hash": "sha256:a1b2c3..."
  }
}
```

**Response:**

```json
{
  "option_id": "opt_001",
  "session_id": "ses_abc123",
  "verdict": "ALLOW",
  "policy_refs": ["pol_001"],
  "warnings": ["Action is not reversible"],
  "modified_action_spec": null,
  "requires_actor": null
}
```

| Field | Type | Description |
|---|---|---|
| `option_id` | string | Echoed option identifier |
| `session_id` | string | Echoed session identifier |
| `verdict` | string | `"ALLOW"`, `"MODIFY"`, `"BLOCK"`, or `"ESCALATE"` |
| `policy_refs` | list[str] | Policy identifiers that matched |
| `warnings` | list[str] | Human-readable warnings |
| `modified_action_spec` | dict \| null | Modified action parameters if verdict is `MODIFY` |
| `requires_actor` | string \| null | Required actor role if verdict is `ESCALATE` |

**Errors:** None (validation errors return verdict `BLOCK` with explanation).

---

### POST /verdict

**Server:** xnch (port 8001)
**Trust required:** Called by Nexi internally (no explicit decorator)
**Description:** Pipeline Step 10: Authoritative policy re-evaluation. This is the final, binding policy check before execution.

**Flow:**
1. Verifies system state version matches the current global version
2. Re-evaluates the action against the active policy (not dry-run mode)
3. Resolves the actor from the governance store
4. If allowed: issues an RS256 execution token with TTL based on the actor's trust level
5. Writes to the Decision Ledger
6. Emits observability event to Langfuse

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | string | **yes** | Client-provided request identifier |
| `actor.id` | string | **yes** | Actor identifier |
| `actor.claimed_role` | string | **yes** | Actor's claimed role |
| `action.type` | string | **yes** | Action type |
| `action.target` | string | **yes** | Action target |
| `action.payload_hash` | string | **yes** | Hash of the action payload |
| `action.payload` | dict | **yes** | Full action payload |
| `context.session_id` | string | **yes** | Session identifier |
| `context.nexi_reasoning_ref` | string | **yes** | Reference to Nexi's reasoning trace |
| `context.system_state_version` | string | **yes** | Current system state version |

**Example request:**

```json
{
  "request_id": "req_abc123",
  "actor": {
    "id": "nexi",
    "claimed_role": "nexi"
  },
  "action": {
    "type": "MEMORY_WRITE",
    "target": "ep_001",
    "payload_hash": "sha256:a1b2c3...",
    "payload": {
      "episode_id": "ep_001",
      "prediction_delta": 0.42
    }
  },
  "context": {
    "session_id": "ses_abc123",
    "nexi_reasoning_ref": "reason_001",
    "system_state_version": "v_abc123def"
  }
}
```

**Response (ALLOW):**

```json
{
  "request_id": "req_abc123",
  "verdict": "ALLOW",
  "verdict_reason": "Action approved. Actor has can_write_memory capability and policy allows MEMORY_WRITE for TRUSTED_AGENT+ roles.",
  "policy_refs": ["pol_001"],
  "modified_action": null,
  "execution_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_ttl_ms": 3600000,
  "audit_ref": "aud_789ghi"
}
```

**Response (BLOCK):**

```json
{
  "request_id": "req_abc123",
  "verdict": "BLOCK",
  "verdict_reason": "Actor lacks permission for action type EXECUTE on target system_config.",
  "policy_refs": ["pol_003"],
  "modified_action": null,
  "execution_token": null,
  "token_ttl_ms": 0,
  "audit_ref": "aud_def456"
}
```

| Field | Type | Description |
|---|---|---|
| `request_id` | string | Echoed request identifier |
| `verdict` | string | `"ALLOW"` or `"BLOCK"` |
| `verdict_reason` | string | Human-readable explanation |
| `policy_refs` | list[str] | Policy identifiers that contributed |
| `modified_action` | dict \| null | Modified action parameters if applicable |
| `execution_token` | string \| null | RS256-signed JWT (only on ALLOW) |
| `token_ttl_ms` | int | Token time-to-live in milliseconds (0 if BLOCK) |
| `audit_ref` | string | UUID audit reference |

**Errors:** `409` STALE_SESSION (version mismatch), `401` unknown actor.

---

## Execution

### POST /execution/outcome

**Server:** xnch (port 8001)
**Trust required:** Called by the execution runner
**Description:** Pipeline Step 13: Receives the execution outcome from the execution runner. Completes the episode in the episodic store, then fires an async callback to Nexi `POST /callback/outcome` for prediction delta computation and potential re-extraction.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `execution_ref` | string | **yes** | — | Execution reference identifier |
| `decision_id` | string | **yes** | — | Decision identifier |
| `execution_token_ref` | string | **yes** | — | Reference to the execution token that authorized this |
| `outcome_status` | string | **yes** | — | Outcome status (e.g., `"SUCCESS"`, `"FAILURE"`, `"PARTIAL"`) |
| `observed_state_delta` | dict | no | `{}` | Key-value pairs of state changes |
| `side_effects_observed` | list[str] | no | `[]` | Side effects detected during execution |
| `duration_ms` | int | no | `0` | Actual execution duration in milliseconds |
| `anomalies` | list[str] | no | `[]` | Anomalies detected during execution |

**Example request:**

```json
{
  "execution_ref": "exec_abc123",
  "decision_id": "dec_abc123",
  "execution_token_ref": "tok_abc123",
  "outcome_status": "SUCCESS",
  "observed_state_delta": {
    "memory_version": "v_002"
  },
  "side_effects_observed": ["triggered_consolidation"],
  "duration_ms": 2340,
  "anomalies": []
}
```

**Response:**

```json
{
  "status": "ok",
  "episode_id": "ep_001"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` if successfully processed |
| `episode_id` | string \| null | Completed episode identifier |

**Errors:** None (errors are logged, response still returns `status: "ok"` with null episode_id).

```bash
# cURL
curl -X POST http://localhost:8001/execution/outcome \
  -H "Content-Type: application/json" \
  -d '{
    "execution_ref": "exec_abc123",
    "decision_id": "dec_abc123",
    "execution_token_ref": "tok_abc123",
    "outcome_status": "SUCCESS",
    "duration_ms": 2340
  }'
```

---

## Governance

### GET /governance/weights

**Server:** xnch (port 8001)
**Trust required:** SYSTEM (by convention; no explicit decorator)
**Description:** Returns the active weight configuration for a given intent class. Weights are used by Nexi during scoring (Pipeline Step 6) to compute the composite score for each option.

**Query parameter:** `intent_class: string` (required)

| Intent Class | Default Weights |
|---|---|
| `EXECUTION` | `{policy_score: 0.25, outcome_score: 0.30, risk_score: 0.35, context_fit_score: 0.10}` |
| `QUERY` | `{policy_score: 0.20, outcome_score: 0.30, risk_score: 0.20, context_fit_score: 0.30}` |
| `DECISION` | `{policy_score: 0.25, outcome_score: 0.35, risk_score: 0.25, context_fit_score: 0.15}` |
| `ESCALATION` | `{policy_score: 0.30, outcome_score: 0.25, risk_score: 0.30, context_fit_score: 0.15}` |

**Response:**

```json
{
  "version": "w_abc123",
  "intent_class": "EXECUTION",
  "weights": {
    "policy_score": 0.25,
    "outcome_score": 0.30,
    "risk_score": 0.35,
    "context_fit_score": 0.10
  }
}
```

**Errors:** None (returns defaults if no custom config is found).

```bash
# cURL
curl -X GET "http://localhost:8001/governance/weights?intent_class=EXECUTION"
```

---

### POST /governance/weights/propose

**Server:** xnch (port 8001)
**Trust required:** SYSTEM
**Description:** Submits a proposed weight configuration for review. Proposals enter a pending state and must be approved via `POST /governance/weights/approve` before they become active.

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `intent_class` | string | **yes** | — | Intent class to apply weights to |
| `weights` | dict | **yes** | — | Weight dict with keys: `policy_score`, `outcome_score`, `risk_score`, `context_fit_score` |
| `episode_batch` | int | no | — | Optional episode batch identifier for traceability |
| `proposed_by` | string | no | `"api"` | Identifier of the proposing entity |

**Response:**

```json
{
  "version": "w_def456",
  "status": "pending"
}
```

| Field | Type | Description |
|---|---|---|
| `version` | string | Version identifier for the proposed config |
| `status` | string | Always `"pending"` |

**Errors:** None.

```bash
# cURL
curl -X POST http://localhost:8001/governance/weights/propose \
  -H "Content-Type: application/json" \
  -d '{
    "intent_class": "EXECUTION",
    "weights": {
      "policy_score": 0.30,
      "outcome_score": 0.25,
      "risk_score": 0.30,
      "context_fit_score": 0.15
    },
    "proposed_by": "learning_subsystem"
  }'
```

---

### POST /governance/weights/approve

**Server:** xnch (port 8001)
**Trust required:** SYSTEM
**Description:** Approves a pending weight configuration. Validates that weights sum to 1.0 and each weight is >= 0.05. On success, deactivates the prior active config for that intent class, activates the new one, and increments the system state version.

**Query parameter:** `version: string` (required)

**Errors:**

| Status | Meaning | Resolution |
|---|---|---|
| `404` | No pending weight config found for the given version | Check version or submit a new proposal |
| `422` | Weights do not sum to 1.0 or a weight is < 0.05 | Adjust weights: sum must be exactly 1.0, each >= 0.05 |

**Response:**

```json
{
  "version": "w_def456",
  "status": "active"
}
```

```bash
# cURL
curl -X POST "http://localhost:8001/governance/weights/approve?version=w_def456"
```

---

### POST /governance/actors

**Server:** xnch (port 8001)
**Trust required:** SYSTEM
**Description:** Upserts an actor in the governance store. Creates a new actor or updates an existing one (on conflict).

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `actor_id` | string | **yes** | Unique actor identifier |
| `role` | string | **yes** | Actor role (e.g., `ADMIN`, `OPERATOR`, `VIEWER`, `AGENT`) |
| `capability_set` | list[str] | **yes** | List of capabilities (e.g., `DEPLOY`, `READ`, `QUERY`, `ADMIN`, `SCHEMA_WRITE`) |

**Example request:**

```json
{
  "actor_id": "deploy_bot",
  "role": "OPERATOR",
  "capability_set": ["DEPLOY", "READ", "QUERY"]
}
```

**Response:**

```json
{
  "status": "ok",
  "actor_id": "deploy_bot"
}
```

**Errors:** None.

```bash
# cURL
curl -X POST http://localhost:8001/governance/actors \
  -H "Content-Type: application/json" \
  -d '{
    "actor_id": "deploy_bot",
    "role": "OPERATOR",
    "capability_set": ["DEPLOY", "READ", "QUERY"]
  }'
```

---

### GET /governance/policy-candidates

**Server:** xnch (port 8001)
**Trust required:** SYSTEM
**Description:** Lists pending policy candidates generated by the learning subsystem. Ordered by `created_at` descending (most recent first).

**Response:** `list[dict]`

```json
[
  {
    "id": "pc_001",
    "rule_expression": "action.type == MEMORY_WRITE AND payload.prediction_delta > 0.3",
    "enforcement_level": "HARD",
    "confidence": 0.82,
    "source": "pattern_extraction",
    "created_at": "2026-06-27T03:00:00Z"
  }
]
```

**Errors:** None.

```bash
# cURL
curl -X GET http://localhost:8001/governance/policy-candidates
```

---

## Environment Variables

### xnch Server Variables (prefix: `XNCH_`)

| Variable | Default | Description |
|---|---|---|
| `XNCH_BASE_DIR` | `~/.xnch` | Root data directory for configuration, keys, and vault |
| `XNCH_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (session cache, KV store, rate limiter) |
| `XNCH_AUTH_SECRET` | `dev-secret-change-in-production` | HS256 shared secret for auth token verification |
| `XNCH_TOKEN_TTL_MS` | `30000` | Default execution token TTL in milliseconds (overridden by trust-level TTL) |
| `XNCH_SESSION_TTL_S` | `120` | Session TTL in seconds before automatic expiry |
| `XNCH_RATE_LIMIT_PER_MINUTE` | `10` | Maximum requests per minute per actor |
| `XNCH_NEXI_BASE_URL` | `http://localhost:8000` | Nexi service base URL for internal callbacks |
| `XNCH_POSTGRES_URL` | `postgresql://localhost:5432/xnch` | PostgreSQL / pgvector connection URL for episodic and graph stores |
| `XNCH_PATTERN_MIN_OBSERVATIONS` | `10` | Minimum observations required before a pattern can be extracted |
| `XNCH_SCORE_ADAPTER_ACCURACY_THRESHOLD` | `0.6` | Accuracy threshold for the score adapter |
| `XNCH_LANGFUSE_PUBLIC_KEY` | `""` | Langfuse observability public key |
| `XNCH_LANGFUSE_SECRET_KEY` | `""` | Langfuse observability secret key |
| `XNCH_LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse host URL for observability events |
| `XNCH_LITELLM_PROXY_URL` | `http://litellm:4000` | LiteLLM proxy base URL (used by nexi_gateway via XNCH config) |
| `XNCH_GRAPH_EXTRACTOR_MODEL` | `ollama/phi3:mini` | Model identifier used for graph extraction |
| `XNCH_VAULT_DIR` | `~/.xnch/vault` | Perception vault directory for storing captured data |
| `XNCH_PERCEPTION_REDIS_DB` | `0` | Redis database number for perception signals |
| `XNCH_ATTENTION_SILENCE_THRESHOLD_S` | `1.5` | Silence threshold in seconds for voice activity detection |
| `XNCH_ATTENTION_SCREEN_DIFF_THRESHOLD` | `0.15` | Screen diff threshold (0.0–1.0) for triggering attention events |
| `XNCH_ATTENTION_IDLE_TIMEOUT_S` | `600` | Idle timeout in seconds for the attention system |

### LiteLLM Variables (no prefix — used by nexi_gateway)

| Variable | Default | Description |
|---|---|---|
| `LITELLM_BASE_URL` | `http://i7-node:4000` | LiteLLM base URL (used by nexi_gateway for chat/stream endpoints) |
| `LITELLM_API_KEY` | `""` | LiteLLM API key for authentication |

### Nexi Server Variables (prefix: `NEXI_`)

| Variable | Default | Description |
|---|---|---|
| `NEXI_XNCH_BASE_URL` | `http://localhost:8001` | xnch service base URL for internal callbacks (memory, policy, verdict) |
| `NEXI_XNCH_PUBLIC_KEY_PATH` | `~/.xnch/keys/public.pem` | Filesystem path to xnch RS256 public key for token validation |
| `NEXI_VLLM_PRIMARY_URL` | `http://localhost:8000/v1` | Primary vLLM endpoint for inference |
| `NEXI_VLLM_PRIMARY_TIMEOUT_S` | `30.0` | Primary vLLM timeout in seconds |
| `NEXI_VLLM_SECONDARY_URL` | `""` | Secondary vLLM endpoint (fallback if primary fails) |
| `NEXI_VLLM_SECONDARY_TIMEOUT_S` | `45.0` | Secondary vLLM timeout in seconds |
| `NEXI_MODEL_ID` | `mistralai/Mistral-7B-Instruct-v0.3` | Default model identifier for inference |
| `NEXI_OPTIONS_COUNT` | `5` | Number of options to generate in the option generation step |
| `NEXI_LITELLM_PROXY_URL` | `http://localhost:4000/v1` | LiteLLM proxy URL for Nexi pipeline |
| `NEXI_LITELLM_PROXY_TIMEOUT_S` | `60.0` | LiteLLM proxy timeout in seconds |
| `NEXI_INTENT_CLASSIFIER_MODEL` | `gemma4-local` | Model identifier used for intent classification |
| `NEXI_SESSION_TTL_S` | `120` | Session TTL in seconds |
| `NEXI_CLARIFICATION_TTL_S` | `120` | Clarification hold TTL in seconds |
| `NEXI_EXECUTION_TOKEN_TTL_MS` | `30000` | Execution token TTL in milliseconds (default, overridden by trust level) |
| `NEXI_REDIS_URL` | `unix:///tmp/xnch-redis.sock` | Redis connection URL (shared with xnch via Unix socket) |
| `NEXI_EXECUTION_RUNNER_URL` | `http://localhost:8002` | Execution runner base URL |
| `NEXI_VLLM_HEALTH_URL` | `http://vllm-gemma4:8000/health` | vLLM health check URL |
| `NEXI_AUDIT_EVENTS_PATH` | `~/.xnch/audit/events.jsonl` | Filesystem path for audit event log (JSONL format) |

---

## Glossary

| Term | Definition |
|---|---|
| **Actor** | An entity that interacts with the system (human or agent). Each actor has an ID, role, trust level, and capability set. |
| **Capability** | A specific permission granted to an actor (e.g., `can_write_memory`, `can_modify_policies`). |
| **Context Manifest** | A snapshot of relevant episodes, patterns, and policies assembled at the start of a decision pipeline. |
| **Decision Ledger** | An append-only log of all verdict decisions and their outcomes. |
| **DAG (Directed Acyclic Graph)** | The compiled execution plan produced by Nexi, describing the sequence of actions to perform. |
| **Episodic Store** | A pgvector-backed database storing episodic memories with semantic search capability. |
| **Execution Token** | An RS256 JWT issued by the verdict endpoint that authorizes a specific action. |
| **Governance Store** | The database of actors, roles, capabilities, weight configs, and policy candidates. |
| **Idempotency Key** | A client-provided key that ensures a request is processed only once, even if retried. |
| **KV Cache** | Redis key-value store used for session caching, deduplication, and rate limiting. |
| **Langfuse** | Observability platform used for tracing and monitoring pipeline execution. |
| **LiteLLM** | A proxy server that provides a unified interface to multiple LLM providers. |
| **Pattern** | A learned behavioral pattern extracted from recurring episodes, with a success rate and confidence score. |
| **Prediction Delta** | The absolute difference (0.0–1.0) between the predicted outcome and the actual outcome of an action. |
| **Proactivity Engine** | A subsystem that surfaces contextually relevant memories and intentions based on current state. |
| **Session** | A scoped interaction context that tracks state, actor, and trace information through the pipeline. |
| **Trust Level** | A hierarchical numeric level (1–5) assigned to actors that determines access to capabilities and endpoints. |
| **vLLM** | A high-throughput LLM serving engine used as the primary inference backend. |
| **Weight Config** | A set of four scoring weights (`policy_score`, `outcome_score`, `risk_score`, `context_fit_score`) per intent class that controls option scoring. |
