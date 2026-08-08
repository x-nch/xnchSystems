# Nexi MCP bridge deploy

External MCP servers are federated into the Nexi runtime via **xnch MCP bridge**.
Nexi chat (`POST /nexi/chat`) sees bridged tools with a configured prefix (e.g. `crg_*`).

## Config

Copy example to gate7:

```bash
cp infra/no-k3s/shared/mcp-servers.example.yaml ~/.xnch/mcp-servers.yaml
```

Env (optional, defaults shown):

```bash
XNCH_MCP_BRIDGE_ENABLED=true
XNCH_MCP_SERVERS_PATH=~/.xnch/mcp-servers.yaml
XNCH_MCP_MAX_TOOL_ROUNDS_WITH_BRIDGE=5
```

Restart xnch after changes:

```bash
sudo systemctl restart xnch.service
```

## Verify

```bash
# CLI (recommended)
python -m cli mcp servers
python -m cli mcp tools --actor nexi --prefix crg_
python -m cli mcp call crg_list_graph_stats_tool
python -m cli mcp call am_memory_recall --arg query="MCP bridge" --arg limit=2
python -m cli mcp test
python -m cli mcp test --skip-chat   # tools only, no LiteLLM

# Shell script (same coverage)
scripts/test-nexi-mcp.sh

# curl
curl -s http://127.0.0.1:8001/mcp/servers | jq .
curl -s http://127.0.0.1:8001/mcp/tools -H 'X-Actor-Role: nexi' | jq '.tools[].name' | grep crg_
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"crg_list_graph_stats_tool","arguments":{}}'
curl -s http://127.0.0.1:8001/mcp/call -H 'X-Actor-Role: nexi' \
  -H 'Content-Type: application/json' \
  -d '{"name":"xnch_health","arguments":{}}' | jq .result.mcp_bridge
```

## code-review-graph (Phase 2)

- Server id: `code-review-graph`
- Prefix: `crg_`
- Tier: `T0_READ`
- Actors: `nexi`, `operator`
- Write/build tools denied in example config

Requires `uvx code-review-graph` on gate7 and a built graph for the repo.

## agentmemory (Phase 3)

- Server id: `agentmemory`
- Prefix: `am_`
- Tier: `T1_WRITE`
- Backend: `http://127.0.0.1:3111` via `npx @agentmemory/mcp`
- **Curated memory** — deploy lessons, architecture, actions (not chat episodic)
- Nexi blocked from `xnch_memory_store_note` — use `am_memory_lesson_save` instead

Full guide: [docs/guides/memory-routing.md](../docs/guides/memory-routing.md)
Runbook: [docs/runbooks/memory-routing-deploy.md](../docs/runbooks/memory-routing-deploy.md)

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"am_memory_recall","arguments":{"query":"Nexi MCP bridge","limit":3}}'
```

## docs-test (Context7-style offline)

- Server id: `docs-test`
- Prefix: `doc_`
- Tier: `T0_READ`
- Local package: `docs_test_mcp/` — no API key, canned snippets for FastAPI/Pydantic/MCP/LiteLLM/Kuzu
- Tools: `doc_resolve-library-id`, `doc_query-docs`

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"doc_resolve-library-id","arguments":{"libraryName":"FastAPI","query":"lifespan"}}'
```

## context7 (live docs, optional)

Set `enabled: true` and `CONTEXT7_API_KEY` in `~/.xnch/mcp-servers.yaml` (get key at context7.com/dashboard).
Tools appear as `c7_resolve-library-id`, `c7_query-docs`.

## Architecture

```
/nexi/chat → chat_with_tools → invoke_tool
                                    ├─ native xnch_* handlers
                                    └─ bridge → stdio MCP child (uvx code-review-graph serve)
```

OpenCode/Cursor may keep direct MCP in `opencode.jsonc`; Nexi runtime uses the bridge only.
