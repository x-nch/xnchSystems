# Quickstart — Local Development

Audience: new devs/agents on the repo. Sources: root `pyproject.toml`,
AGENTS.md dev commands, `tests.md`. Everything here should be run before
deploying anywhere ([Node A](deploy-node-a.md) / [Node B](deploy-node-b.md)).

## 0. Prerequisites

- Python **3.13+**, `uv`
- A local Redis (`redis-server`) for full-stack runs; unit tests use `fakeredis`
- PostgreSQL + pgvector only if you exercise L2 paths locally
- Node.js 20+ only for `web/`

## 1. Clone with submodules

```bash
git clone https://github.com/x-nch/xnchSystems && cd xnchSystems
git submodule update --init --recursive   # pulls xnch/ and nexi/
```

## 2. Install & test

```bash
uv sync
pytest -x --no-header        # expect the known pre-existing failures listed in
                             # reference/tests.md — anything else is a regression
```

## 3. Run the two services locally

```bash
redis-server &                       # or your own instance; see XNCH_REDIS_URL
uv run python -m xnch.main           # control plane :8001  (needs Postgres for L2)
NEXI_XNCH_BASE_URL=http://localhost:8001 uv run python -m nexi.main   # :8000
```

Health checks:

```bash
curl -sf http://localhost:8001/health
curl -sf http://localhost:8000/health
```

Minimal env for local runs (placeholders):

```bash
export XNCH_AUTH_SECRET='<dev-secret>'
# export XNCH_POSTGRES_URL='postgresql://<user>:<pw>@localhost:5432/xnch'
```

## 4. Try the chat surface

> The CLI imports the `xnch` submodule at runtime — from a fresh clone make it
> importable (`PYTHONPATH=./xnch` + its runtime deps) or use an operator env
> that already carries them [UNVERIFIED remedy]. `xtrain` is self-contained.

```bash
uv run xnch-cli health
uv run xnch-cli auth token      # mint an actor token
uv run xnch-cli chat "hello"    # goes through /nexi/chat tool loop
```

Copy-paste routing prompts: [nexi-test-prompts](nexi-test-prompts.md).

## 5. Optional surfaces

```bash
cd web && npm install && npm run dev          # muse UI (gateway proxy needs
                                              # XNCH_GATEWAY_URL / _SECRET)
(cd xnch-train && uv run xtrain --help)      # training pipeline CLI (self-contained env)
python -m xnch_mcp --help                     # stdio MCP server for editors
```

## Where next

- Deploy for real: [Node A](deploy-node-a.md) → [Node B](deploy-node-b.md)
- Understand the machine: [architecture overview](../architecture/overview.md)
