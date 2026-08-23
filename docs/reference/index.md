# Reference Index

Lookup material. Schemas live in code beside each handler; these pages are maps.

| Page | Contents |
|---|---|
| [api-xnch](api-xnch.md) | xnch REST surface by router (:8001): session, memory, policy, verdict, execution, goals, governance, workflows/approvals, admin, voice |
| [api-gateway-chat](api-gateway-chat.md) | `/v1/chat/completions`, `/nexi/chat(+stream)` tool loop, voice routes, nexi :8000 endpoints, muse proxy |
| [auth-model](auth-model.md) | HS256 actor bearers, RS256 execution tokens, Hybrid-B gateway tokens, tool tiers, guards, header matrix |
| [mcp-http-api](mcp-http-api.md) | `/mcp/*` endpoints, headers, curl examples |
| [mcp-tools](mcp-tools.md) | native + bridged tool catalog, actor matrix, routing |
| [mcp-config](mcp-config.md) | MCP-related `XNCH_*` env vars and YAML files |
| [env-vars](env-vars.md) | exhaustive `XNCH_*` / `NEXI_*` / `XTRAIN_*` / `SCRAPER_*` + unprefixed |
| [config-files](config-files.md) | `~/.xnch/*.yaml` inventory + compose-side config |
| [cli-reference](cli-reference.md) | `python -m cli …`, `xtrain …`, scripts |
| [tests](tests.md) | suites, commands, known pre-existing failures |

Related elsewhere:

- Architecture: [overview](../architecture/overview.md) ·
  [memory](../architecture/memory.md) · [workflows & HITL](../architecture/workflows-hitl.md) ·
  [data model](../architecture/data-model.md) · [training](../architecture/training.md)
- Guides: [quickstart dev](../guides/quickstart-dev.md) ·
  [chat & tools](../guides/chat-and-tools.md) · [operate HITL](../guides/operate-hitl.md) ·
  [build workflow](../guides/build-workflow.md) · [run eval](../guides/run-eval.md)
- Runbooks: [restart Node A](../runbooks/restart-node-a.md) /
  [Node B](../runbooks/restart-node-b.md) · [GPU window](../runbooks/gpu-window.md) ·
  [e2e smoke](../runbooks/e2e-smoke.md) · [rollback](../runbooks/rollback.md)
- Immutable records: [docs index](../index.md#immutable-records-link-only)

Legacy diagram sources: [`diagrams/mcp-bridge.mmd`](../diagrams/mcp-bridge.mmd);
the old single-file diagram suite has been superseded by
[`architecture/`](../architecture/overview.md).
