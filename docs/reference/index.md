# Reference — xnch MCP

HTTP API, tool catalog, and configuration for the xnch MCP layer on gate7 (`:8001`).

## MCP

| Doc | Contents |
|-----|----------|
| [mcp-tools.md](mcp-tools.md) | Native + bridged tool catalog, actor matrix, routing |
| [mcp-http-api.md](mcp-http-api.md) | `/mcp/*` endpoints, headers, curl examples |
| [mcp-config.md](mcp-config.md) | Env vars (`XNCH_*`) and YAML policy files |
| [memory-routing.md](../guides/memory-routing.md) | Episodic vs agentmemory tool routing |

## Related guides

| Doc | Contents |
|-----|----------|
| [MCP bridge architecture](../guides/mcp-bridge.md) | Request flow, server inventory, tiers |
| [MCP CLI](../guides/mcp-cli.md) | `python -m cli mcp servers\|tools\|call\|test` |
| [Nexi test prompts](../guides/nexi-test-prompts.md) | Copy-paste chat prompts for tool routing |
| [MCP bridge deploy](../runbooks/mcp-bridge-deploy.md) | Gate7 bridge + CRG graph rebuild |
| [Memory routing deploy](../runbooks/memory-routing-deploy.md) | Episodic vs agentmemory verify |
| [Web search deploy](../runbooks/web-search-deploy.md) | SearXNG + `xnch_web_search` |

## Architecture

- [Architecture diagram suite](../architecture-suite.md) — system, infra, memory, MCP bridge
- [mcp-bridge.mmd](../diagrams/mcp-bridge.mmd) — Nexi tool-loop sequence

## OpenCode handoff

- [misc/opencode/xnch-mcp-handoff.md](../../misc/opencode/xnch-mcp-handoff.md) — stdio MCP setup for editors
