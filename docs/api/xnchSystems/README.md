# xnchSystems API docs

Meta/repo-level documentation for the **xnchSystems** monorepo: how the pieces
talk to each other across the Mac, gate7 (Node A), and Node B. This covers the
monorepo *glue* (CLI, scripts, cross-cutting proxy routes, env vars, HTTP
surfaces that span both nodes) — not the full internals of the `xnch` or
`nexi` packages.

## Documents

| Doc | Purpose |
|-----|---------|
| [overview.md](overview.md) | Architecture of the multi-node API surface (Mac / Node A / Node B), port map, traffic flow, package map |
| [cli.md](cli.md) | `python -m cli` (alias `xnch-cli`) command reference with examples and config |
| [endpoints.md](endpoints.md) | Top-level HTTP endpoints reachable from the Mac (base `http://192.168.1.10:8001`) |
| [auth.md](auth.md) | Auth headers and tokens: HS256 JWT, RS256 execution tokens, internal-token and media-gateway bearer auth |

## Quick orientation

- **Mac** runs the CLI / voice client. It talks to **gate7 (Node A)** at
  `http://192.168.1.10:8001` (xnch control plane) over the home LAN.
- **Node A (gate7)** runs `xnch` (:8001), LiteLLM (:4000), Redis (:6379),
  PostgreSQL (:5432). Reachable from Node B on the node link at
  `192.168.50.1`.
- **Node B** runs `nexi` (:8000), vLLM Ornith (:8082), vLLM Qwen-VL (:8083),
  media-gateway (:8090), ComfyUI (:8188), fs-read-agent (:8003), exec-agent
  (:8004). Reachable from Node A on the node link at `192.168.50.2`.

## Source of truth

Endpoints were read from:

- `xnch/routes/*.py`, `xnch/main.py`, `xnch/config.py`
- `nexi/main.py`, `nexi/config.py`
- `cli/{main.py, client.py, config.py}`
- `xnch_mcp/http_router.py`
- `fs_read_agent/server.py`, `exec_agent/server.py`
- `media-gateway/media_gateway/{main.py, config.py, routes.py}`
- `infra/no-k3s/node-{a,b}/systemd/*.service`
- `scripts/setup-mac-voice-client.sh`, `scripts/media-node-b-agent.sh`

When a behavior is ambiguous, docs mark it `TODO` instead of guessing.
