# xnchSystems HTTP endpoints

Top-level endpoints reachable from the **Mac**. Base URL
`http://192.168.1.10:8001` (gate7 = Node A). All routes below are served by
`xnch.main:app` (`xnch` package + `xnch_mcp` bridge) unless noted.

Auth notes: many routes accept the auth token in the `Authorization` header;
`/session/init` takes it in the JSON body field `auth_token`; `/mcp/*` uses the
`X-Actor-Role` header. Full rules in [auth.md](auth.md).

## xnch control plane (Node A :8001)

### Health & state

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| GET | `/health` | Liveness + deps | `{status, redis, version, ...}` |
| GET | `/system/state` | System/policy versions | `{system_state_version, policy_version}` |

### Sessions & decision pipeline

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| POST | `/session/init` | Run decision pipeline | Req `{auth_token, raw_input, input_type="TEXT", priority="NORMAL", source_system, trace_id?, idempotency_key?}`; Resp `{status, decision_id?, execution_ref?, audit_ref?, hold_id?, error?}` |
| POST | `/session/{session_id}/clarify` | Amend a session with clarification | Req `{amended_input, ...}` |
| POST | `/verdict` | Authorize an action, issue execution token | Req `{request_id, actor, action, context}`; 409 `STALE_SESSION` on version mismatch |
| GET/POST | `/policy/check` | Evaluate a policy filter | Req `{session_id, system_state_version, actor_role, option_id, action}` |

### Execution

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| POST | `/execution/execute` | Execute a decision (stub) | TODO: exact request fields |
| POST | `/execution/outcome` | Report execution result | Req `{execution_ref, decision_id, execution_token_ref, outcome_status, observed_state_delta, side_effects_observed, duration_ms, anomalies}` |

### Memory

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| POST | `/memory/read` | Store-backed memory read | Req `{session_id, actor_id, actor_role, query}` |
| POST | `/memory/write` | Write a memory/episode | Req `{session_id, actor_id, write_type, payload}` |
| GET | `/memory/graph/stats` | Knowledge-graph stats | TODO: exact fields |
| GET | `/memory/graph/entities` | List graph entities | TODO: params |
| GET | `/memory/graph/relations` | List graph relations | TODO: params |
| GET | `/memory/graph/subgraph` | Fetch subgraph | TODO: params |
| GET | `/memory/graph/stream` | SSE graph stream | TODO: events |

### Governance (incl. HITL pipeline)

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| GET | `/governance/weights?intent_class=` | Current weights | TODO: exact response |
| POST | `/governance/weights/propose` | Propose weight change | TODO: exact request |
| POST | `/governance/weights/approve` | Approve a proposal | TODO: exact request |
| POST | `/governance/actors` | Register/update actor | TODO: exact request |
| GET | `/governance/policy-candidates` | Candidate policies | TODO: exact response |
| POST | `/governance/pipeline/invoke` | Invoke HITL pipeline step | TODO: exact request |
| POST | `/governance/pipeline/resume` | Resume HITL pipeline | TODO: exact request |
| GET | `/governance/pipeline/{thread_id}` | HITL pipeline state | TODO: exact response |

### Auth / admin

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| GET | `/auth/public-key` | RS256 execution-token public key | `{algorithm: "RS256", public_key_pem}` |
| POST | `/admin/consolidate` | Trigger memory consolidation | TODO |
| POST | `/admin/reseed-identity` | Reseed actor identity | TODO |

## Cross-node / Nexi bridge (xnch → nexi, LiteLLM)

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| POST | `/nexi/chat` | Chat with Nexi (LLM via LiteLLM) | Req `{session_id, message, actor_role="operator"}`; Resp `{response, session_id}` |
| POST | `/nexi/chat/stream` | Streaming chat | SSE `data: {content}` … `data: [DONE]` |
| GET | `/nexi/system-prompt` | Current system prompt | TODO |
| GET | `/nexi/capabilities` | Nexi capabilities | TODO |
| GET | `/nexi/memory/surface` | Pending proactivity events | `[{...event...}]` |
| POST | `/nexi/memory/recall` | Semantic memory recall | Req `{query, top_k=5}`; Resp `[{similarity, type, content, ...}]` |
| POST | `/nexi/voice/transcribe` | STT (multipart) | Multipart `audio` + `format`, `sample_rate`; Resp `{text, ...}` |
| POST | `/nexi/voice/speak` | TTS | Req `{text, voice?}`; Resp audio bytes |
| POST | `/nexi/voice/speak/upload` | TTS upload variant | TODO |
| POST | `/nexi/voice/chat` | Full voice turn (multipart) | Multipart `audio` + `session_id`, `actor_role`, `return_audio` |
| POST | `/v1/chat/completions` | OpenAI-compatible chat | Req `{model, messages:[{role, content}]}`; requires Bearer |

## MCP bridge (`xnch_mcp/http_router.py`, prefix `/mcp`)

Actor-aware MCP tool routing. Headers: `X-Actor-Role` (required),
`X-Trace-Id`, `X-Session-Id` (optional).

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| GET | `/mcp/tools` | Tools available to actor | `{actor, tools: [{name, tier, ...}]}` |
| GET | `/mcp/tools/openai` | Tools as OpenAI function schema | `{tools: [...]}` |
| GET | `/mcp/servers` | Bridge server status | `{enabled, servers: [{server_id, connected, tool_count, tool_prefix}]}` |
| POST | `/mcp/call` | Invoke one tool | Req `{name, arguments}`; Resp `{result}` |
| POST | `/mcp/call/batch` | Invoke many tools | TODO: exact request |

Tool families include `xnch_*`, `crg_*` (code-review-graph), `am_*`
(agentmemory), `doc_*` (docs), plus web search. `cli/mcp_tests.py` expects
≥3 connected servers and ≥35 tools for actor `nexi`.

## Node B sidecars (NOT on the Mac base URL)

Reachable from Mac only via xnch MCP tools / Node A proxy, not directly
(they bind `127.0.0.1` by default; `media-gateway` binds LAN and is reachable
at `http://192.168.50.2:8090`).

### nexi decision engine (Node B :8000)

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| GET | `/health` | Liveness | `{status, ...}` |
| POST | `/session/start` | Start a nexi session (called by xnch) | TODO: exact request |
| POST | `/callback/outcome` | Execution outcome callback | TODO: exact request |

### fs-read-agent (Node B :8003) — `X-Internal-Token` header

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness `{status, host}` |
| GET | `/list?path=&recursive=&max_entries=` | List directory |
| GET | `/read?path=&offset=&max_bytes=` | Read file (max 10 MiB) |
| GET | `/stat?path=` | File stat |
| GET | `/exists?path=` | Existence check |
| GET | `/glob?pattern=&max_results=` | Glob |

Enforced by `infra/no-k3s/shared/fs-policy.yaml` (403 on denied paths).

### exec-agent (Node B :8004) — `X-Internal-Token` header

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| GET | `/health` | Liveness `{status, host}` |
| POST | `/run` | Run a governed command | Req `{command, cwd?}`; 403 on policy deny, 408 on timeout |

Enforced by `infra/no-k3s/shared/exec-policy.yaml`.

### media-gateway (Node B :8090) — Bearer `MEDIA_GATEWAY_TOKEN`

| Method | Path | Purpose | Shape |
|--------|------|---------|-------|
| GET | `/health` | Liveness | `{status, ...}` |
| POST | `/media/files` | Upload a file (png/jpg/jpeg/webp/mp4/mov) | multipart |
| POST | `/media/jobs` | Create a media job | TODO: exact body |
| GET | `/media/jobs` | List jobs | TODO |
| GET | `/media/jobs/{id}` | Job status/result | TODO |
| GET | `/media/files/{id}` | Download a file | TODO |

All `/media/*` routes fail closed (503 `gateway token not configured`) when
`MEDIA_GATEWAY_TOKEN` is unset. Orchestrates Qwen-VL (:8083) + ComfyUI
(:8188) via LiteLLM (`MEDIA_GATEWAY_LITELLM_URL`, default
`http://127.0.0.1:8083/v1`).

## Not part of this surface

- `xnch` internals such as perception/vault-indexer routes — see
  `docs/api/xnch/`.
- `nexi` full pipeline internals — see `docs/api/nexi/`.
