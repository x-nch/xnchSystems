# Config Files Reference

Runtime configuration beyond env vars lives in YAML under `~/.xnch/` on each
node. Templates: `infra/no-k3s/shared/*.example.yaml`. Sources: config paths in
`xnch/config.py` / `nexi/config.py`, deploy runbooks.

| File | Node(s) | Owner knob | Contents |
|---|---|---|---|
| `~/.xnch/xnch.env` | A | — | service env (see [env-vars](env-vars.md)) |
| `~/.xnch/nexi.env` | B | — | nexi + exec/fs agents env |
| `~/.xnch/mcp-servers.yaml` | A | `XNCH_MCP_SERVERS_PATH` / `NEXI_MCP_SERVERS_PATH` | federated MCP servers: id, command, prefix, tier, actors, enabled ([bridge](../architecture/mcp-bridge.md#server-inventory)) |
| `~/.xnch/memory-routing.yaml` | A | `XNCH_MEMORY_ROUTING_POLICY_PATH` | episodic vs agentmemory tool routing rules |
| `~/.xnch/exec-policy.yaml` | A+B | `XNCH_EXEC_POLICY_PATH` | governed commands: per-host prefix allowlist (status/read-only ops), denied destructive substrings, cwd lock, timeout |
| `~/.xnch/fs-policy.yaml` | A+B | `XNCH_FS_POLICY_PATH` | read-only FS scope for fs agent/tools |
| `~/.xnch/web-search.yaml` | A | `XNCH_WEB_SEARCH_POLICY_PATH` | `xnch_web_search` policy (SearXNG backend) |
| `~/.xnch/policies/*.yaml` | A | `policies_dir` | policy-engine rule packs (first-match-wins; candidates land here via governance approval) |
| `~/.xnch/nexi-capabilities.generated.yaml` | B | `NEXI_CAPABILITIES_GENERATED_PATH` | auto-refreshed capability manifest (do not hand-edit) |

Node-A compose-side config (not `~/.xnch`):

| File | Purpose |
|---|---|
| `infra/no-k3s/node-a/litellm-config/config.yaml` + `shared/litellm-routing.yaml` | litellm models; Node B target `api_base http://192.168.50.2:8082/v1`; served name must be vLLM's `openai/ornith-1.0-35b`, alias `qwen3-xml` is public-facing only |
| `infra/no-k3s/node-a/searxng/settings.yml` | SearXNG settings (loopback bind) |
| `~/.xnch/xnch.env` secrets | POSTGRES_PASSWORD, LANGFUSE_*, LITELLM_MASTER_KEY, XNCH_AUTH_SECRET |

Character/persona (in nexi submodule, deployed with it):
`nexi/character/{persona,capabilities,identity_facts}.yaml` — identity +
`never_do` rules, tool inventory/routing, canonical facts seeded to pgvector.

Key/data dirs created under `XNCH_BASE_DIR`: `keys/` (RSA pair), `audit/`
(events.jsonl + decision ledger), `governance/`, `weights/`, `data/`
(SQLite stores), `graph.kuzu`.
