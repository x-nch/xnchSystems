# MCP Configuration Reference — xnch

Environment variables and YAML files that configure the xnch MCP layer (native tools,
external server bridge, governed fs/exec, and web search).

Related: [mcp-tools.md](mcp-tools.md), [mcp-http-api.md](mcp-http-api.md), [mcp-bridge architecture](../architecture/mcp-bridge.md).

## Contents

- [Env vars](#env-vars)
- [YAML files](#yaml-files)
- [mcp-servers.yaml](#mcp-serversyaml)
- [web-search.yaml](#web-searchyaml)
- [fs-policy.yaml](#fs-policyyaml)
- [exec-policy.yaml](#exec-policyyaml)
- [Index note](#index-note)

---

## Env vars

Settings come from `xnch/config.py` (`BaseSettings`, `env_prefix="XNCH_"`, loads
`.env`). Env vars override YAML defaults; explicit env (e.g. `LITELLM_API_KEY`)
overrides settings.

### MCP bridge

| Env var | Setting | Default | Purpose |
|---------|---------|---------|---------|
| `XNCH_MCP_BRIDGE_ENABLED` | `mcp_bridge_enabled` | `true` | Master switch for the external MCP bridge |
| `XNCH_MCP_SERVERS_PATH` | `mcp_servers_path` | `~/.xnch/mcp-servers.yaml` | Path to bridge server definitions |
| `XNCH_MCP_MAX_TOOL_ROUNDS` | `mcp_max_tool_rounds` | `3` | Max chat tool-loop rounds (explicit override) |
| `XNCH_MCP_MAX_TOOL_ROUNDS_WITH_BRIDGE` | `mcp_max_tool_rounds_with_bridge` | `5` | Rounds when the bridge is active (and no explicit `XNCH_MCP_MAX_TOOL_ROUNDS`) |

### Web search

| Env var | Setting | Default | Purpose |
|---------|---------|---------|---------|
| `XNCH_WEB_SEARCH_POLICY_PATH` | `web_search_policy_path` | `~/.xnch/web-search.yaml` | Web search policy file |
| `XNCH_SEARXNG_URL` | `searxng_url` | `http://127.0.0.1:8888` | Declared in settings; **not yet merged into the running policy** — set `searxng_url` in `web-search.yaml` instead |

### Memory routing

| Env var | Setting | Default | Purpose |
|---------|---------|---------|---------|
| `XNCH_MEMORY_ROUTING_POLICY_PATH` | `memory_routing_policy_path` | `~/.xnch/memory-routing.yaml` | Episodic vs agentmemory routing policy |
| `XNCH_AM_PREFETCH_ENABLED` | `am_prefetch_enabled` | `false` | Inject up to 2 agent lessons into chat context via `am_memory_lesson_recall` |

### Read-only filesystem (xnch_fs_*)

| Env var | Setting | Default |
|---------|---------|---------|
| `XNCH_FS_POLICY_PATH` | `fs_policy_path` | `~/.xnch/fs-policy.yaml` |
| `XNCH_FS_LOCAL_HOST` | `fs_local_host` | `node-a` |
| `XNCH_FS_AGENT_NODE_B_URL` | `fs_agent_node_b_url` | `http://192.168.50.2:8003` |
| `XNCH_FS_AGENT_TOKEN` | `fs_agent_token` | `""` |

### Governed execution (xnch_exec_run)

| Env var | Setting | Default |
|---------|---------|---------|
| `XNCH_EXEC_POLICY_PATH` | `exec_policy_path` | `~/.xnch/exec-policy.yaml` |
| `XNCH_EXEC_LOCAL_HOST` | `exec_local_host` | `node-a` |
| `XNCH_EXEC_AGENT_NODE_B_URL` | `exec_agent_node_b_url` | `http://192.168.50.2:8004` |
| `XNCH_EXEC_AGENT_TOKEN` | `exec_agent_token` | `""` |

### Stdio server / chat loop (not `XNCH_`-prefixed)

| Env var | Used by | Default | Purpose |
|---------|---------|---------|---------|
| `XNCH_BASE_URL` | `xnch_mcp/stdio_server.py` | `http://127.0.0.1:8001` | HTTP backend for the stdio MCP server |
| `XNCH_ACTOR` | `xnch_mcp/auth.py` | `external` | Actor role for the stdio server (set `opencode`) |
| `LITELLM_BASE_URL` | `xnch_mcp/chat_tools.py` | `settings.litellm_proxy_url` | LiteLLM proxy base for the tool loop |
| `LITELLM_API_KEY` / `LITELLM_MASTER_KEY` | `xnch_mcp/chat_tools.py` | `""` | Auth for the chat loop |

Restart xnch after changing any of these:

```bash
sudo systemctl restart xnch.service
```

---

## YAML files

All files live under `~/.xnch/` and are seeded from `infra/no-k3s/shared/`
(deploy via `cp`, not symlink — they carry secrets/tokens).

---

## mcp-servers.yaml

External MCP bridge server definitions. Loaded by
`xnch_mcp/bridge/config.py` → `McpBridgePool`. Each server:

| Field | Type | Notes |
|-------|------|-------|
| `enabled` | bool | Include in bridge (default true) |
| `actors` | list[str] | Who may use these tools (default `nexi`, `operator`) |
| `tier` | string | `T0_READ` / `T1_WRITE` / `T2_EXEC` (aliases `T0`/`T1`/`T2`) |
| `tool_prefix` | string | Prefix prepended to remote tool names (default `<server_id>_`) |
| `command` / `args` | string / list | Stdio subprocess command |
| `env` | dict | Extra env for the child process |
| `allow_tools` | list | Allowlist of remote tool names (omit = allow all not denied) |
| `deny_tools` | list | Denylist of remote tool names |

Example (abridged — full example in `infra/no-k3s/shared/mcp-servers.example.yaml`):

```yaml
servers:
  code-review-graph:
    enabled: true
    actors: [nexi, operator]
    tier: T0_READ
    tool_prefix: crg_
    command: /home/x-nch/.local/bin/uvx
    args: [code-review-graph, serve, --repo, /home/x-nch/xnchSystems]
    env: {}
    allow_tools: [query_graph_tool, semantic_search_nodes_tool, get_architecture_overview_tool]
    deny_tools: [build_or_update_graph_tool, refactor_tool, apply_refactor_tool]

  agentmemory:
    enabled: true
    actors: [nexi, operator]
    tier: T1_WRITE
    tool_prefix: am_
    command: /usr/bin/npx
    args: [-y, "@agentmemory/mcp"]
    env:
      AGENTMEMORY_URL: http://127.0.0.1:3111
      AGENTMEMORY_SECRET: <secret>
    deny_tools: [memory_governance_delete, memory_heal, memory_export]

  docs-test:
    enabled: true
    actors: [nexi, operator]
    tier: T0_READ
    tool_prefix: doc_
    command: /home/x-nch/xnchSystems/xnch/.venv/bin/python
    args: [-m, docs_test_mcp]
    allow_tools: [resolve-library-id, query-docs]

  context7:
    enabled: false          # enable + set CONTEXT7_API_KEY to activate
    actors: [nexi, operator]
    tier: T0_READ
    tool_prefix: c7_
    command: /usr/bin/npx
    args: [-y, "@upstash/context7-mcp"]
    env: {CONTEXT7_API_KEY: ""}
    allow_tools: [resolve-library-id, query-docs]
```

---

## web-search.yaml

`xnch_mcp/web/policy.py`. Falls back to `infra/no-k3s/shared/web-search.example.yaml`
if the configured path is missing.

| Field | Default | Notes |
|-------|---------|-------|
| `enabled` | `true` | Disable to hide `xnch_web_search` |
| `backend` | `searxng` | Only `searxng` supported |
| `searxng_url` | `http://127.0.0.1:8888` | SearXNG base URL |
| `max_results` | `5` | Default result count |
| `max_results_cap` | `10` | Hard cap enforced by the handler |
| `timeout_s` | `15` | SearXNG timeout |
| `safesearch` | `1` | SearXNG safesearch level |
| `engines` | — | Engines (e.g. duckduckgo, brave, wikipedia) |
| `allowed_actors` | `[nexi, operator]` | Actors allowed to call `xnch_web_search` |

---

## memory-routing.yaml

`xnch/memory/routing_policy.py`. Falls back to `infra/no-k3s/shared/memory-routing.example.yaml`.

| Field | Default | Notes |
|-------|---------|-------|
| `primary` | `xnch_episodic` | Runtime chat memory (pgvector) |
| `curated` | `agentmemory` | Cross-session agent notes (`am_*`) |
| `deprecate_store_note_for` | `[nexi]` | Actors blocked from `xnch_memory_store_note` |

See [memory-routing guide](../guides/memory-routing.md).

---

## fs-policy.yaml

`xnch_mcp/fs/policy.py`. Read-only filesystem roots and deny globs for `xnch_fs_*`.
Roots are per-host (`node-a`, `node-b`); deny globs hide `.ssh/`, keys, `.env*`,
`credentials*`, etc.

```yaml
hosts:
  node-a:
    roots: [/home/x-nch, /etc/systemd/system]
  node-b:
    roots: [/home/x-nch, /etc/systemd/system]
deny_globs:
  - "**/.ssh/**"
  - "**/keys/**"
  - "**/*.pem"
  - "**/id_rsa*"
  - "**/.gnupg/**"
  - "**/.env"
  - "**/.env.*"
  - "**/xnch.env"
  - "**/nexi.env"
  - "**/credentials*"
```

---

## exec-policy.yaml

`xnch_mcp/exec/policy.py`. Allowlist for `xnch_exec_run`. Rejects shell metacharacters
(`;`, `|`, `&`, backtick, `$(`, redirects) and destructive commands
(`sudo`, `rm`, `chmod/chown`, `kubectl apply|delete`, `terraform apply|destroy`,
`systemctl start|stop|restart`, `docker compose up/down`, `docker run/exec/rm`,
`pip/apt install`, `shutdown`, `reboot`, `mkfs`, `dd`).

Commands must match an `allowed_prefixes` entry for the target host (e.g.
`systemctl status`, `journalctl`, `curl -sf`, `git status`, `pytest`, `nvidia-smi` on
node-b). Full allowlist in `infra/no-k3s/shared/exec-policy.yaml`.

---

## Index note

See [index.md](index.md) for the full reference index.
