# OpenCode handoff: xnch MCP

## Package

`xnch_mcp/` (not `mcp/` — avoids PyPI `mcp` SDK name clash)

## Stdio (OpenCode / Cursor)

Configured in [`opencode.jsonc`](../../opencode.jsonc):

```json
"xnch": {
  "type": "local",
  "command": ["/home/x-nch/xnchSystems/.venv/bin/python", "-m", "xnch_mcp"],
  "env": {
    "XNCH_BASE_URL": "http://127.0.0.1:8001",
    "XNCH_ACTOR": "opencode"
  }
}
```

Requires xnch running on :8001. Stdio server calls HTTP `/mcp/call` (thin client).

## HTTP API (Nexi runtime + stdio backend)

| Endpoint | Method | Headers | Purpose |
|----------|--------|---------|---------|
| `/mcp/tools` | GET | `X-Actor-Role` | List tools for actor |
| `/mcp/tools/openai` | GET | `X-Actor-Role` | OpenAI tool schema list |
| `/mcp/call` | POST | `X-Actor-Role`, `X-Trace-Id?`, `X-Session-Id?` | Invoke tool |
| `/mcp/call/batch` | POST | `X-Actor-Role` | Invoke multiple tools |
| `/mcp/servers` | GET | — | Bridge server status |

## Tools (native, 13 total)

| Tool | Tier | Actors | Purpose |
|------|------|--------|---------|
| `xnch_health` | T0 | all | Health + Redis; includes `mcp_bridge`/`web_search` |
| `xnch_status` | T0 | all | state/policy versions |
| `xnch_memory_recall` | T0 | all | pgvector episodic — chat continuity |
| `xnch_memory_surface` | T0 | all | pending proactivity events |
| `xnch_memory_store_note` | T1 | opencode, operator, admin, agent (**not nexi**) | manual pgvector note |
| `xnch_session_run` | T2 | nexi, operator, admin | governed decision pipeline |
| `xnch_fs_list` / `read` / `stat` / `exists` / `glob` | T0 | nexi, operator, admin | read-only filesystem on node-a/node-b |
| `xnch_exec_run` | T2 | nexi, operator, admin | allowlisted shell command |
| `xnch_web_search` | T0 | nexi, operator | SearXNG metasearch |

## Dual memory (important)

| Store | Tools | Auto in chat? |
|-------|-------|---------------|
| pgvector episodic | `xnch_memory_*` | Yes |
| agentmemory curated | `am_*` (bridged) | No |

**Nexi** cannot call `xnch_memory_store_note` (403) — use `am_memory_lesson_save` for deploy lessons.

See [docs/guides/memory-routing.md](../../docs/guides/memory-routing.md).

## Bridged prefixes (nexi/operator only — not visible to opencode)

Configured in `~/.xnch/mcp-servers.yaml`; see [mcp-bridge deploy](../../docs/runbooks/mcp-bridge-deploy.md).

| Prefix | Server | Tier | Example tools |
|--------|--------|------|---------------|
| `crg_` | code-review-graph | T0_READ | `crg_query_graph_tool`, `crg_detect_changes_tool` |
| `am_` | agentmemory | T1_WRITE | `am_memory_lesson_save`, `am_memory_lesson_recall` |
| `doc_` | docs-test (offline) | T0_READ | `doc_resolve-library-id`, `doc_query-docs` |
| `c7_` | context7 (live docs) | T0_READ | disabled by default |

Full catalog: [docs/reference/mcp-tools.md](../../docs/reference/mcp-tools.md).

## Nexi chat tool loop

`/nexi/chat` and `/nexi/chat/stream` use `xnch_mcp.chat_tools.chat_with_tools`:
- Actor `nexi` (SYSTEM trust)
- Max rounds: 3 default, **5 when MCP bridge active**
- pgvector recall injected in `assemble_context`; optional `XNCH_AM_PREFETCH_ENABLED` for agent lessons

## Verify

```bash
cd /home/x-nch/xnchSystems
export PYTHONPATH=/home/x-nch/xnchSystems:/home/x-nch/xnchSystems/xnch
pytest xnch_mcp/tests/test_memory_routing.py -q
python -m cli mcp test --skip-chat
curl -s http://127.0.0.1:8001/mcp/tools -H 'X-Actor-Role: opencode'
```

## Entry points

- `python -m xnch_mcp` — stdio MCP server
- `xnch-mcp` — same (after `pip install -e .`)

## See also

- [memory-routing.md](../../docs/guides/memory-routing.md)
- [memory-routing-deploy.md](../../docs/runbooks/memory-routing-deploy.md)
- [mcp-tools.md](../../docs/reference/mcp-tools.md)
- [mcp-http-api.md](../../docs/reference/mcp-http-api.md)
- [mcp-config.md](../../docs/reference/mcp-config.md)
- [mcp-bridge.md](../../docs/guides/mcp-bridge.md)
