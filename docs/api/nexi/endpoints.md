# Nexi HTTP API reference

Base URL (Node B): `http://<node-b>:8000`

All request/response bodies are JSON. Nexi exposes exactly **five** routes,
defined in `nexi/main.py`:

| Method | Path | Summary | Response model |
|--------|------|---------|----------------|
| `POST` | `/session/start` | Entry point called by xnch after actor resolution — runs the full decision pipeline | `SessionStartResponse` |
| `POST` | `/callback/outcome` | Step 14 — xnch fires this after writing an execution outcome to episodic store; nexi writes a prediction delta back | `{"status": "ok"}` |
| `GET` | `/health` | Liveness/version | `{"status": "ok", "version": "0.1.0"}` |
| `GET` | `/nexi/capabilities` | Realtime merged capabilities snapshot (live probe status via the refresh loop) | free-form dict |
| `POST` | `/nexi/refresh` | On-demand full refresh: topology → tools → probes → overlay write | free-form dict |

> `ClarifyRequest` (`nexi/main.py:81`) is defined but **not bound to any route**.
> TODO: intended for a clarification flow that is not yet exposed.

---

## `POST /session/start`

Runs the full decision pipeline (see [pipeline.md](pipeline.md)) and returns an
intermediate "verdict" to the caller. xnch is the primary caller.

### Request body — `SessionStartRequest`

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | UUID (string) | Session identifier |
| `trace_id` | UUID (string) | Correlation id, threaded through audit events |
| `actor` | object | `{id, role, capability_set}` — already resolved by xnch |
| `system_state_version` | string | Pinned state version; stale version triggers `STALE_SESSION` retry |
| `policy_version` | string | Policy set version |
| `raw_input` | string | User's raw utterance |
| `priority` | string | Default `"NORMAL"` |
| `idempotency_key` | UUID (string) | Idempotency key |

The body is validated as `SessionContext` (`model_validate`), so wire format ==
`SessionContext` fields (see [models.md](models.md)).

Example:

```bash
curl -s -X POST http://192.168.50.2:8000/session/start \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "3f9b6f52-...",
    "trace_id": "a1b2c3d4-...",
    "actor": {"id": "test-user", "role": "OPERATOR", "capability_set": ["DEPLOY", "READ"]},
    "system_state_version": "v1.0.0",
    "policy_version": "v1.0.0",
    "raw_input": "deploy service myservice",
    "priority": "NORMAL",
    "idempotency_key": "9e4f...-..."
  }'
```

### Response body — `SessionStartResponse`

| Field | Type | Notes |
|-------|------|-------|
| `status` | string | `EXECUTING` \| `CLARIFICATION_REQUIRED` \| `ESCALATED` \| `ERROR` |
| `decision_id` | UUID \| null | Present when `status == EXECUTING` |
| `execution_ref` | UUID \| null | Present when dispatched |
| `estimated_completion_ms` | int \| null | Mean duration of completed manifest episodes, else `30000` |
| `audit_ref` | UUID \| null | xnch verdict audit reference |
| `clarification_required` | bool | `true` when intent was ambiguous |
| `hold_id` | UUID \| null | Present when escalated (all blocked / verdict BLOCK / escalation triggered) |
| `error` | string \| null | `ERROR` detail |

### Status → meaning

| HTTP | Response `status` | When |
|------|-------------------|------|
| 200 | `EXECUTING` | Pipeline completed, dispatched for execution |
| 200 | `CLARIFICATION_REQUIRED` | Intent interpreter raised `ClarificationRequired` |
| 200 | `ESCALATED` | All options blocked, selector escalated, or xnch verdict `BLOCK` |
| 200 | `ERROR` | Intent interpreter not available (lifespan not run) |
| 409 | — | `STALE_SESSION: retry failed` — fresh context reload + verdict resubmit also failed |
| 422 | — | Plan compilation failed (`PlanCompilationError`) or compiled DAG empty |
| 500 | — | Selected option not found after selection |
| 502 | — | Verdict submission to xnch failed (non-`STALE_SESSION` error) |
| 503 | — | Context manifest load failed (hard stop, no fallback) |

> Note: a `PolicyViolation` raised by the intent interpreter's injection scan
> (`nexi/pipeline/intent_interpreter.py`) is **not caught** in this endpoint and
> would surface as HTTP 500. TODO: confirm intended handling.

### Downstream calls made by this endpoint

1. `POST {NEXI_XNCH_BASE_URL}/memory/read` — context manifest (hard stop on failure)
2. `GET {NEXI_XNCH_BASE_URL}/governance/weights?intent_class=…` — weight config (optional; fallback to defaults on failure)
3. `POST {NEXI_LITELLM_PROXY_URL}/chat/completions` — option generation (fallback chain: LiteLLM → vLLM → llama.cpp → rule-based)
4. `POST {NEXI_XNCH_BASE_URL}/policy/check` — dry-run per option, in parallel
5. `POST {NEXI_XNCH_BASE_URL}/verdict` — verdict + execution token
6. `POST {NEXI_EXECUTION_RUNNER_URL}/execute` — execution dispatch (on `401 TOKEN_EXPIRED` nexi re-submits verdict and retries once; on connect failure it records a stub outcome to xnch instead)

---

## `POST /callback/outcome`

Step 14. xnch calls this after it has written the execution outcome to its
episodic store. Nexi computes a prediction delta and writes it back to xnch
memory.

### Request body

Free-form dict (no Pydantic model). Recognized keys:

| Key | Type | Notes |
|-----|------|-------|
| `trace_id` | string | Defaults to `"unknown"` |
| `outcome_score_predicted` | float | Default `0.5` |
| `outcome_status` | string | `"SUCCESS"` ⇒ actual `1.0`, else `0.0` |
| `session_id` | string | Required for the memory write |
| `episode_id` | string | Required for the memory write |
| `actor` | object | Defaults to `{id:"system", role:"AGENT", capability_set:[]}` |
| `system_state_version` | string | Default `""` |
| `policy_version` | string | Default `""` |

`prediction_delta = |outcome_score_predicted - actual_success|` and
`early_flag = prediction_delta > 0.3` are written via
`POST {NEXI_XNCH_BASE_URL}/memory/write` (`write_type: EPISODE_PREDICTION_UPDATE`).

### Response

```json
{"status": "ok"}
```

> On memory-write failure nexi logs the error and relies on the caller to retry
> with backoff. Code contains `# TODO: enqueue for exponential backoff retry (max 5 attempts)`.

### Example

```bash
curl -s -X POST http://192.168.50.2:8000/callback/outcome \
  -H 'Content-Type: application/json' \
  -d '{
    "trace_id": "a1b2c3d4-...",
    "session_id": "3f9b6f52-...",
    "episode_id": "c5d6e7f8-...",
    "outcome_score_predicted": 0.75,
    "outcome_status": "SUCCESS",
    "actor": {"id": "system", "role": "AGENT", "capability_set": []}
  }'
# => {"status": "ok"}
```

---

## `GET /health`

Liveness + version probe.

```bash
curl -s http://192.168.50.2:8000/health
```

Response:

```json
{"status": "ok", "version": "0.1.0"}
```

---

## `GET /nexi/capabilities`

Returns the merged operational capabilities snapshot. If the auto-refresh loop
has populated `_capability_state` (i.e. `NEXI_CAPABILITY_AUTO_REFRESH=true`, the
default), it returns the freshly built capabilities dict; otherwise it falls
back to `load_capabilities()` — the static `capabilities.yaml` base merged with
the generated overlay.

```bash
curl -s http://192.168.50.2:8000/nexi/capabilities
```

Response shape (free-form dict, **not** a Pydantic model — built by
`nexi/character/capability_builder.py::build_capabilities`):

| Key | Type | Notes |
|-----|------|-------|
| `generated_at` | string (ISO-8601) | Snapshot timestamp |
| `sources` | object | `{tool_inventory, infra_manifests, policies}` — where each input came from |
| `hosts` | object | `{host: {role, label, services: {name: ip:port}}}` per discovered host |
| `tools` | object | Tools grouped by category (`memory`, `filesystem`, `execution`, `code_graph`, …) |
| `bridge` | object | `{active, servers: {id: {prefix, connected}}}` — MCP bridge status |
| `tool_routing` | string | Routing hints mapping intent → tool group |
| `filesystem` | object | `{read_only, roots, path_prefix, deny_globs}` from fs-policy |
| `exec` | object | `{timeout_seconds, denied_substrings}` from exec-policy |
| `status` | object | Live probe results: `{healthy: [...], down: [...], checked_at}` |

When it falls back to `load_capabilities()` the dict instead has the
`capabilities.yaml` shape (`summary`, `hosts`, `filesystem`, `tools`,
`tool_routing`, `voice`, `status`, …) merged with the generated overlay keys.

---

## `POST /nexi/refresh`

Runs an on-demand full refresh (topology → tools → probes → overlay write) and
returns a compact summary. This is the same work `_capability_refresh_loop`
performs periodically (`NEXI_PROBE_INTERVAL_S`, `NEXI_CAPABILITY_REFRESH_INTERVAL_S`),
but forced (`force_write=True`) and synchronous.

```bash
curl -s -X POST http://192.168.50.2:8000/nexi/refresh
```

Response:

```json
{
  "status": "ok",
  "generated_at": "2026-08-14T12:34:56Z",
  "hosts": ["node-a", "node-b"],
  "healthy": ["xnch", "postgres", "redis", "vllm-qwen", "..."],
  "down": ["media-gateway"]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `status` | string | Always `"ok"` on success (errors raise HTTPException upstream) |
| `generated_at` | string | `caps["generated_at"]` |
| `hosts` | list[str] | Sorted host names from the snapshot |
| `healthy` | list[str] | Services that answered a probe with HTTP < 500 |
| `down` | list[str] | Services that did not respond or returned ≥ 500 |

The refresh path (`nexi/main.py::_refresh_capabilities`) also writes the
generated overlay to `NEXI_CAPABILITIES_GENERATED_PATH` and emits an audit
`CAPABILITIES_UPDATED` event only when the content changed.

---

## Not HTTP here

- **Eval harness** — CLI only: `python -m nexi.eval.cli --fixture` (see [overview.md](overview.md#eval-cli)).
- **Proactivity engine** (`nexi/proactivity/engine.py`) — a library; queuing to
  Redis keys `proactivity:pending:*`. No FastAPI route in `nexi/main.py`.
- **Context assembly / chat** (`nexi/pipeline/context_assembler.py`) — library
  used by the chat path (owned by xnch), not wired to nexi's routes.
