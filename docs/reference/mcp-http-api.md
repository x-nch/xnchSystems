# MCP HTTP API Reference — xnch

The `xnch_mcp` router is mounted on xnch (`:8001`) under the `/mcp` prefix
(`xnch/main.py` includes `xnch_mcp/http_router.py`). Both the Nexi runtime chat loop
and the stdio MCP server (`python -m xnch_mcp`, used by OpenCode/Cursor) back onto
these endpoints.

Base URL for all examples: `http://127.0.0.1:8001` (gate7).

Related: [mcp-tools.md](mcp-tools.md), [mcp-config.md](mcp-config.md), [mcp-bridge architecture](../guides/mcp-bridge.md).

## Contents

- [Headers](#headers)
- [GET /mcp/tools](#get-mcptools)
- [GET /mcp/tools/openai](#get-mcptoolsopenai)
- [POST /mcp/call](#post-mcpcall)
- [Memory tools](#memory-tools)
- [POST /mcp/call/batch](#post-mcpcallbatch)
- [GET /mcp/servers](#get-mcpservers)
- [Nexi chat tool loop](#nexi-chat-tool-loop)
- [xnch_health payload](#xnch_health-payload)
- [Index note](#index-note)

---

## Headers

| Header | Required | Default | Purpose |
|--------|----------|---------|---------|
| `X-Actor-Role` | no (default `external`) | `external` | Actor identity; drives tier + `allowed_actors` filtering |
| `X-Trace-Id` | no | generated `uuid4` | Trace correlation for event log / audit |
| `X-Session-Id` | no | — | Session context for the call |
| `Content-Type` | on POST | — | `application/json` |

Actors: `nexi` (SYSTEM), `operator`/`admin` (OWNER), `opencode`/`agent`
(TRUSTED_AGENT), `viewer` (EXTERNAL_AGENT), `external` (UNTRUSTED). See the
[actor matrix](mcp-tools.md#actor-matrix) for what each can call.
---

## GET /mcp/tools

List tools visible to an actor (name, description, tier).

```bash
# opencode actor (direct MCP backend)
curl -s http://127.0.0.1:8001/mcp/tools -H 'X-Actor-Role: opencode' | jq '.tools[].name'

# nexi actor (Nexi runtime — includes bridged crg_*/am_*/doc_*)
curl -s http://127.0.0.1:8001/mcp/tools -H 'X-Actor-Role: nexi' | jq '.tools[].name' | grep -E 'crg_|am_|doc_'
```

Response shape:

```json
{
  "actor": "nexi",
  "tools": [
    {"name": "xnch_health", "description": "Check xnch service health including Redis connectivity.", "tier": "T0_READ"}
  ]
}
```

---

## GET /mcp/tools/openai

List tools in OpenAI function-calling schema (used by `chat_with_tools` to build the
`tools` payload for LiteLLM).

```bash
curl -s http://127.0.0.1:8001/mcp/tools/openai -H 'X-Actor-Role: nexi' \
  | jq '.tools[] | select(.function.name=="xnch_memory_recall")'
```

Response shape:

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "xnch_memory_recall",
        "description": "Semantic search over episodic memory (pgvector).",
        "parameters": {"type": "object", "properties": {...}, "required": ["query"], "additionalProperties": false}
      }
    }
  ]
}
```

---

## POST /mcp/call

Invoke a single tool. Body: `{"name": string, "arguments": object}`.

```bash
# opencode actor — native tool
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: opencode' -H 'Content-Type: application/json' \
  -H 'X-Trace-Id: curl-001' -H 'X-Session-Id: sess-1' \
  -d '{"name":"xnch_health","arguments":{}}' | jq .result

# nexi actor — native memory recall
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_memory_recall","arguments":{"query":"MCP bridge","top_k":3}}' | jq .result

# nexi actor — bridged tool (code-review-graph)
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"crg_list_graph_stats_tool","arguments":{}}' | jq .result

# nexi actor — bridged tool (agentmemory)
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"am_memory_recall","arguments":{"query":"Nexi MCP bridge","limit":2}}' | jq .result

# operator actor — governed session run (T2_EXEC)
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: operator' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_session_run","arguments":{"input":"check cluster health"}}' | jq .result
```

Success response:

```json
{"name": "xnch_health", "result": {...}}
```

Errors:

| HTTP | Raised from | Detail |
|------|-------------|--------|
| `400` | `ValueError` | Unknown tool, missing/invalid arguments |
| `403` | `PermissionError` | Actor cannot invoke tool (tier or `allowed_actors`) |
| `500` | other `Exception` | Handler/service failure |

---

## Memory tools

Two independent stores — see [memory-routing guide](../guides/memory-routing.md).

### Episodic (pgvector) — `xnch_memory_*`

Auto-recalled in every `/nexi/chat` turn. Audit field: `"memory_target": "episodic"`.

```bash
# recall chat history
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_memory_recall","arguments":{"query":"MCP bridge deploy","top_k":5}}' | jq .

# operator manual pgvector note (nexi gets 403)
curl -s -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_memory_store_note","arguments":{"text":"deploy lesson"}}'
# → 403: use am_memory_lesson_save
```

### Curated (agentmemory) — `am_memory_*`

Explicit tool calls only. Backend `http://127.0.0.1:3111` via MCP bridge stdio proxy.
Audit field: `"memory_target": "agentmemory"`. Tool descriptions prefixed
`[agentmemory/curated]`.

```bash
# save a deploy lesson
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"am_memory_lesson_save","arguments":{"content":"Rebuild CRG after adding packages","context":"deploy"}}' | jq .

# recall lessons
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"am_memory_lesson_recall","arguments":{"query":"CRG graph","limit":3}}' | jq .
```

### Audit `memory_target`

`TOOL_CALL` / `TOOL_CALL_FAILED` events for `xnch_memory_*` and `am_memory_*` include:

```json
{
  "tool": "am_memory_lesson_recall",
  "actor": "nexi",
  "tier": "T1_WRITE",
  "memory_target": "agentmemory",
  "bridge": true,
  "mcp_server": "agentmemory",
  "original_tool": "memory_lesson_recall"
}
```

---

## POST /mcp/call/batch

Invoke multiple tools in one request. Body is an array of the same `ToolCallRequest`
shape; returns an array of `{name, result}`.

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call/batch \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '[{"name":"xnch_status","arguments":{}},{"name":"xnch_memory_surface","arguments":{}}]' | jq .
```

---

## GET /mcp/servers

Bridge server status. Returns `enabled` plus one row per configured server:
`server_id`, `enabled`, `connected`, `tool_prefix`, `tool_count`, `actors`, `tier`.

```bash
curl -s http://127.0.0.1:8001/mcp/servers | jq .

# CLI equivalent
python -m cli mcp servers
```

Response shape:

```json
{
  "enabled": true,
  "servers": [
    {
      "server_id": "code-review-graph",
      "enabled": true,
      "connected": true,
      "tool_prefix": "crg_",
      "tool_count": 14,
      "actors": ["nexi", "operator"],
      "tier": "T0_READ"
    }
  ]
}
```

---

## Nexi chat tool loop

`POST /nexi/chat` (and `/nexi/chat/stream`) run `chat_with_tools` with actor `nexi`.
Body: `{"session_id": string, "message": string, "actor_role": string}` (actor_role
defaults to `operator` and is used only for memory-write guarding).

The loop advertises native + bridged tools (OpenAI schema) to the model and executes
tool calls until the model returns text or `max_rounds` is reached (3 normally, **5
when the bridge is active**). See [mcp-bridge architecture](../guides/mcp-bridge.md).

```bash
curl -s -X POST http://127.0.0.1:8001/nexi/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"sess-demo","message":"which tools query code structure?"}' | jq .
```

```json
{"response": "...", "model_used": "nexi-ornith", "session_id": "sess-demo"}
```

Supporting memory endpoints (pgvector — same store as `xnch_memory_recall`):

```bash
# semantic recall (HTTP shortcut, not MCP tool loop)
curl -s -X POST http://127.0.0.1:8001/nexi/memory/recall \
  -H 'Content-Type: application/json' \
  -d '{"query":"MCP bridge deploy","top_k":3}' | jq .

# pending proactivity events
curl -s http://127.0.0.1:8001/nexi/memory/surface | jq .
```

Chat auto-stores each turn to pgvector; agentmemory requires `am_*` tool calls or
`XNCH_AM_PREFETCH_ENABLED=true` for lesson injection. See
[memory-routing-deploy.md](../runbooks/memory-routing-deploy.md).

---

## xnch_health payload

`xnch_health` includes the bridge and web-search status blocks. Check everything in
one call:

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_health","arguments":{}}' | jq .result
```

```json
{
  "status": "ok",
  "redis": "ok",
  "state_version": "v3.1",
  "version": "0.1.0",
  "mcp_bridge": {
    "enabled": true,
    "tool_count": 27,
    "servers": [
      {
        "server_id": "code-review-graph",
        "enabled": true,
        "connected": true,
        "tool_prefix": "crg_",
        "tool_count": 14,
        "actors": ["nexi", "operator"],
        "tier": "T0_READ"
      }
    ]
  },
  "web_search": {
    "enabled": true,
    "backend": "searxng",
    "searxng_url": "http://127.0.0.1:8888",
    "max_results": 5,
    "engines": ["duckduckgo", "brave", "wikipedia"],
    "allowed_actors": ["nexi", "operator"]
  }
}
```

If the bridge is not started, `mcp_bridge` is `{"enabled": false, "servers": []}`. If
web search is not configured, the `web_search` block is omitted.

---

## Index note

See [index.md](index.md) for the full reference index.
