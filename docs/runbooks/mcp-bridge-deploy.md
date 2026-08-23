# Nexi MCP Bridge — Gate7 Deploy Runbook

Deployment, rebuild, and verification for the **xnch MCP bridge** on gate7
(xnch `:8001`, Nexi runtime via `POST /nexi/chat`).

- Architecture deep-dive: [Nexi MCP Bridge — Architecture Guide](../architecture/mcp-bridge.md) (Session 1)
- API reference: [`docs/reference/mcp-http-api.md`](../reference/mcp-http-api.md)
- CLI reference: [`docs/guides/mcp-cli.md`](../guides/mcp-cli.md)
- Copy-paste chat prompts: [`docs/guides/nexi-test-prompts.md`](../guides/nexi-test-prompts.md)

---

## Live state (checked 2026-08-08)

| Server | Prefix | Tier | Tools | Status |
|--------|--------|------|-------|--------|
| code-review-graph | `crg_` | T0_READ | 14 | connected |
| agentmemory | `am_` | T1_WRITE | 11 | connected |
| docs-test | `doc_` | T0_READ | 2 | connected |
| context7 | `c7_` | T0_READ | 0 | disabled |

**40 tools** exposed to `nexi`: **13 native** (`xnch_*`) + **27 bridged**
(`crg_*` 14 + `am_*` 11 + `doc_*` 2).

CRG graph: **89 files**, **344 nodes** (includes `xnch_mcp/`). Rebuild with
`uvx code-review-graph build && uvx code-review-graph embed` after adding new packages
to the repo index.

> **Note:** If `crg_callers_invoke_tool` fails, the graph was likely built before
> `xnch_mcp/` was git-tracked. Re-run step 2 and restart xnch.

---

## Prerequisites

| Component | Requirement | Why |
|-----------|-------------|-----|
| `uvx` | `/home/x-nch/.local/bin/uvx` (v0.11.6) | Runs `code-review-graph serve` |
| `npx` | `/usr/bin/npx` (v11.16.0) | Runs `@agentmemory/mcp` and `@upstash/context7-mcp` |
| `agentmemory.service` | active on `:3111` | Backend for `am_*` tools (unit `/etc/systemd/system/agentmemory.service`) |
| Repo venv | `/home/x-nch/xnchSystems/xnch/.venv/bin/python` | Runs `docs_test_mcp` and the `python -m cli` tooling |
| Bridge config | `~/.xnch/mcp-servers.yaml` | Server declarations (see step 1) |
| CRG graph | `~/.xnch/xnchSystems/.code-review-graph/` | Built graph for the repo (see step 2) |

**Full paths in YAML are mandatory.** The bridge spawns servers as stdio
subprocesses from under `xnch.service`, which runs in a minimal systemd `PATH`.
A bare `command: uvx` or `command: npx` resolves to nothing and the server shows
`down`. Every `command` in `~/.xnch/mcp-servers.yaml` must be an absolute path:

- `/home/x-nch/.local/bin/uvx`
- `/usr/bin/npx`
- `/home/x-nch/xnchSystems/xnch/.venv/bin/python`

Quick prerequisite check:

```bash
/home/x-nch/.local/bin/uvx --version
/usr/bin/npx --version
systemctl is-active agentmemory.service
systemctl is-active xnch.service
curl -s http://127.0.0.1:8001/health | head -c 200; echo
```

---

## 1. Copy the bridge config

```bash
cp infra/no-k3s/shared/mcp-servers.example.yaml ~/.xnch/mcp-servers.yaml
```

**Expected:** file exists, owned by `x-nch`, not world-writable:

```bash
ls -l ~/.xnch/mcp-servers.yaml
# -rw------- 1 x-nch x-nch ... /home/x-nch/.xnch/mcp-servers.yaml
```

**Failure:** permission denied → `mkdir -p ~/.xnch` first. Wrong owner → `chown
x-nch:x-nch ~/.xnch/mcp-servers.yaml`.

Optional env overrides (defaults already apply; set them in
`/home/x-nch/.xnch/xnch.env` only to change behaviour):

```bash
XNCH_MCP_BRIDGE_ENABLED=true              # default true
XNCH_MCP_SERVERS_PATH=~/.xnch/mcp-servers.yaml
XNCH_MCP_MAX_TOOL_ROUNDS_WITH_BRIDGE=5    # tool-loop cap while bridge is active
```

`mcp-servers.yaml` uses `~/.xnch` as `$HOME`; with systemd the `EnvironmentFile`
`/home/x-nch/.xnch/xnch.env` is what actually reaches the service.

---

## 2. Rebuild the CRG graph (build + embed)

The bridge's `code-review-graph` server reads the graph in
`/home/x-nch/xnchSystems/.code-review-graph/` (gitignored). Build it at the repo
root so it tracks `/home/x-nch/xnchSystems` — the same path `serve --repo`
uses:

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/.local/bin/uvx code-review-graph build
/home/x-nch/.local/bin/uvx code-review-graph embed
```

- `build` re-parses all tracked files (full rebuild). `update` is the faster
  incremental variant when only a few files changed.
- `embed` computes local vector embeddings (all-MiniLM-L6-v2) so
  `crg_semantic_search_nodes_tool` works. Needs the `code-review-graph[embeddings]`
  extra installed in the uvx environment.
- `.code-review-graph/` is gitignored — the database is machine-local state, not
  committed.

**Expected (build):** no errors; **expected (embed):** `Embeddings: N nodes
embedded`.

**Verify graph stats without the bridge:**

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/.local/bin/uvx code-review-graph status
```

**Failure:** `Failed to open database` / `database is locked` → the running
`serve` subprocess (under xnch) holds `graph.db`. Build while the service is up
is normally fine; if you hit a lock, `sudo systemctl restart xnch` first, then
build.

---

## 3. Restart xnch

```bash
sudo systemctl restart xnch.service
systemctl is-active xnch.service          # expect: active
```

**Expected:** bridge connects on startup. Log lines:

```bash
journalctl -u xnch.service -n 100 --no-pager | grep -i "mcp bridge"
# MCP bridge connected: code-review-graph
# MCP bridge connected: agentmemory
# MCP bridge connected: docs-test
# MCP bridge started (3 servers, 27 tools)
```

**Failure:** `MCP bridge failed to start <server>: ...` for one server → the pool
continues with the remaining servers (startup failure of one does not take the
bridge down). See [Troubleshooting](#troubleshooting).

---

## 4. Verify with the CLI test suite

Run from the repo root with the repo venv. `--skip-chat` runs the 11 tool-level
cases only and does **not** need LiteLLM/Ornith:

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp test --skip-chat
```

**Expected (all green after graph includes `xnch_mcp/`):**

```
✓ bridge servers
✓ tool count
✓ xnch_health
✓ crg_list_graph_stats
✓ crg_semantic_search
✓ crg_callers_invoke_tool
✓ am_memory_recall
✓ doc_resolve_library
✓ doc_query_docs
✓ xnch_web_search
✓ web_search_health

Result: 11 passed, 0 failed
```

If `crg_callers_invoke_tool` fails, re-run [step 2](#2-rebuild-the-crg-graph-build--embed)
so `xnch_mcp/registry.py::invoke_tool` is indexed, then restart xnch.

Run the full suite (adds two live `/nexi/chat` tool-loop cases) only when the LLM
path is healthy:

```bash
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp test
```

**Failure:** any `✗` → match the case name against
[Troubleshooting](#troubleshooting). The suite exits non-zero when any case
fails.

---

## 5. Smoke checks (curl)

```bash
# Server status
curl -s http://127.0.0.1:8001/mcp/servers | jq '.servers[] | {server_id, connected, tool_count}'

# Tools visible to nexi (40 = 13 native + 27 bridged)
curl -s http://127.0.0.1:8001/mcp/tools -H 'X-Actor-Role: nexi' | jq '.tools | length'

# One bridged tool
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"crg_list_graph_stats_tool","arguments":{}}'

# Bridge + web search summary from xnch_health
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_health","arguments":{}}' | jq '.result | {mcp_bridge, web_search}'
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Server shows `down`; `uvx`/`npx` binary not found in journal | Command is not an absolute path; systemd `PATH` is minimal | Use the absolute `command` from `mcp-servers.example.yaml` (`/home/x-nch/.local/bin/uvx`, `/usr/bin/npx`); verify with `ls -l`; `sudo systemctl restart xnch` |
| `uvx: command not found` in your shell | `~/.local/bin` not on `PATH` | `export PATH="$HOME/.local/bin:$PATH"`, or call `/home/x-nch/.local/bin/uvx` directly; install: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **CRG graph stale / 0 nodes** — `crg_query_graph_tool` returns `status: not_found`, `crg_list_graph_stats_tool` shows 0 nodes, or `crg_semantic_search_nodes_tool` returns no results | Graph built before the code existed (e.g. built at an earlier commit; `xnch_mcp/` added after) | Rebuild: `cd /home/x-nch/xnchSystems && uvx code-review-graph build && uvx code-review-graph embed`, then `sudo systemctl restart xnch` so the `serve` subprocess reopens the rebuilt `graph.db` |
| **Bridge stop crash** — `stop()` during shutdown throws, or one server flips `down` while others stay `connected` | A single stdio child crashed; supervisor logs `MCP bridge supervisor error (<server>)` | This is **by design**: `pool.stop()` suppresses per-client errors and one crashed child does not take down the pool. Check `journalctl -u xnch.service`, then `sudo systemctl restart xnch` to reconnect the dead server |
| **`input_schema` vs `inputSchema` attr** — bridged tools register but `parameters`/argument schema is empty, or a dependency bump drops schemas | `mcp.types.Tool` exposes the schema as `input_schema` (newer SDK) or `inputSchema` (older SDK); code assumed one name | `_tool_input_schema()` in `xnch_mcp/bridge/pool.py:175` already falls back via `getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)` with an empty-schema default. Never hardcode one attribute name; restart xnch after an `mcp` package bump |
| `tool count` test fails (`< 35` tools) | A server not connected, or `allow_tools`/`deny_tools` filtered tools out | `python -m cli mcp servers` to see per-server state; check the YAML allow/deny lists in `~/.xnch/mcp-servers.yaml` |
| `crg_semantic_search` no results | Embeddings never computed | Run `uvx code-review-graph embed`; verify `Embeddings: N nodes embedded` in `list_graph_stats` |
| `context7` permanently `down` | Server `enabled: false` (default) and/or empty `CONTEXT7_API_KEY` | Leave disabled, or set `enabled: true` + key from context7.com/dashboard and restart xnch |
| All servers `down` immediately after `restart` | Bridge config unreadable (YAML error, wrong `$HOME` expansion, missing file) | `python -m cli mcp servers` → `MCP bridge disabled`; validate: `python -c "import yaml; yaml.safe_load(open('/home/x-nch/.xnch/mcp-servers.yaml'))"` |

---

## Rollback

```bash
sudo systemctl stop xnch.service
cp ~/.xnch/mcp-servers.yaml ~/.xnch/mcp-servers.yaml.bak   # keep the old config
sudo systemctl start xnch.service
```

To disable the bridge entirely, set `XNCH_MCP_BRIDGE_ENABLED=false` in
`/home/x-nch/.xnch/xnch.env` and restart xnch.

---

## 6. Verify memory routing

After bridge is up, confirm dual-memory policy (see
[memory-routing-deploy.md](memory-routing-deploy.md)):

```bash
# nexi blocked from manual pgvector notes
curl -s -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_memory_store_note","arguments":{"text":"test"}}'
# expect 403

python -m cli mcp call am_memory_lesson_recall --arg query="MCP bridge" --arg limit=1
# expect lessons array
```

---

## See also

- [Nexi MCP Bridge — Architecture Guide](../architecture/mcp-bridge.md) — request flow, actor/tier model, tool prefixing & audit, lifecycle
- [MCP CLI reference](../guides/mcp-cli.md) — `python -m cli mcp servers|tools|call|test`
- [Memory routing deploy runbook](memory-routing-deploy.md) — episodic vs agentmemory
- [Web search deploy runbook](web-search-deploy.md) — SearXNG + `xnch_web_search`
- [Nexi test prompts](../guides/nexi-test-prompts.md) — copy-paste chat prompts
- API reference: [`docs/reference/mcp-http-api.md`](../reference/mcp-http-api.md)
- Diagram: `docs/diagrams/mcp-bridge.mmd`
- Source notes: `misc/notes/nexi-mcp-bridge.md`
