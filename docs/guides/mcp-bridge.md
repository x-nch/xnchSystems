# Nexi MCP Bridge — Architecture Guide

The **xnch MCP bridge** federates external MCP servers into the Nexi runtime tool
loop. Nexi chat (`POST /nexi/chat` on gate7, xnch `:8001`) sees external tools with a
server prefix (e.g. `crg_query_graph_tool`) alongside native `xnch_*` tools, and
invokes them over a long-lived stdio subprocess.

Source of truth: `xnch_mcp/bridge/`, `xnch_mcp/registry.py`, `xnch_mcp/chat_tools.py`,
and `~/.xnch/mcp-servers.yaml`. The code-review-graph repo root is
`/home/x-nch/xnchSystems` (the CRG serve path).

## Contents

- [Why the bridge exists](#why-the-bridge-exists)
- [Request flow](#request-flow)
- [Server inventory](#server-inventory)
- [Actor & tier model](#actor--tier-model)
- [Tool prefixing & audit](#tool-prefixing--audit)
- [Tool round bump (3 → 5)](#tool-round-bump-3--5)
- [Lifecycle & health](#lifecycle--health)
- [Nexi character integration](#nexi-character-integration)
- [See also](#see-also)

---

## Why the bridge exists

Interactive agents (OpenCode, Cursor) talk to MCP servers **directly** over stdio.
`xnch_mcp` itself is exposed to them that way (`opencode.jsonc` runs
`python -m xnch_mcp` with `XNCH_ACTOR=opencode`), and they can add their own MCP
servers in their editor config.

The **Nexi runtime** has no such client. `nexi :8000` and the xnch chat gateway have
no external MCP client of their own, so they cannot see the editor's servers. The
bridge gives the Nexi tool loop its own MCP client:

| Consumer | MCP access | How |
|----------|-----------|-----|
| OpenCode / Cursor | Direct stdio | `python -m xnch_mcp` + editor-configured MCP servers |
| Nexi runtime (nexi :8000, xnch :8001) | Bridge only | `xnch_mcp.bridge` spawns each external server as a stdio child |

Servers are declared in `~/.xnch/mcp-servers.yaml`. Each enabled server is spawned as
a stdio subprocess, its tools are listed, renamed with a prefix, filtered by actor and
tier, and merged into the shared tool registry that `chat_with_tools` advertises to
the model.

---

## Request flow

```
POST /nexi/chat ──► chat_with_tools ──► list_openai_tools (native ∪ bridged)
                       │                      │
                       │                      └── LiteLLM /chat/completions
                       ▼
                 parse tool_calls (OpenAI JSON or <tool_call>{json}</tool_call> XML)
                       │
                       ▼
                 invoke_tool(name, args)
                       │
              ┌────────┴─────────┐
              │ native xnch_*    │ bridged (crg_* / am_* / doc_* / c7_*)
              │ handler          │
              └────────┬─────────┘ McpBridgePool.invoke → strip prefix → original name
                       │            McpServerClient.call_tool → stdio session
                       ▼            (uvx code-review-graph serve | npx agentmemory | …)
                 serialize_call_result → JSON-friendly payload
                       │
                       ▼
                 tool_result_message → append → next round
```

1. **`chat_with_tools`** (`xnch_mcp/chat_tools.py`) runs the LiteLLM chat loop with
   `actor_role="nexi"`. Tools come from `list_openai_tools("nexi")`, which merges the
   native registry (`xnch_mcp/registry.py` `_all_tools()`) with every tool in the
   bridge pool (`McpBridgePool.all_tools()`).
2. The model returns either text or `tool_calls`. `parse_tool_calls_from_message`
   handles both the OpenAI JSON form and the `<tool_call>{json}</tool_call>` XML form
   (qwen3_xml parser).
3. `invoke_tool` (`registry.py:70`) looks the name up in the merged tool set, checks
   actor permission, times the call, and dispatches to the tool's handler.
4. Bridged handlers (`pool.py:_make_handler`) forward to `McpBridgePool.invoke`, which
   maps the **prefixed** name back to the **original** remote name and calls the owning
   server's client.
5. `McpServerClient.call_tool` sends the call over the long-lived MCP stdio session;
   `serialize_call_result` (`bridge/result.py`) converts the `CallToolResult` to a
   JSON-friendly payload (single text parsed as JSON when possible; `is_error`
   becomes `{"error": true, ...}`).
6. The result is appended as a `tool` role message and the loop repeats until the model
   returns text or `max_rounds` is exhausted.

A per-call `TOOL_CALL` event is emitted to the event log (see [audit](#tool-prefixing--audit)).

---

## Server inventory

Defined in `~/.xnch/mcp-servers.yaml` (example: `infra/no-k3s/shared/mcp-servers.example.yaml`).

| Server | ID | Prefix | Tier | Actors | Command | Tools | Status |
|--------|----|--------|------|--------|---------|-------|--------|
| code-review-graph | `code-review-graph` | `crg_` | T0_READ | nexi, operator | `uvx code-review-graph serve --repo /home/x-nch/xnchSystems` | 14 (read-only) | enabled |
| agentmemory | `agentmemory` | `am_` | T1_WRITE | nexi, operator | `npx @agentmemory/mcp` → `http://127.0.0.1:3111` | 11 | enabled |
| docs-test | `docs-test` | `doc_` | T0_READ | nexi, operator | `python -m docs_test_mcp` (offline, no API key) | 2 | enabled |
| context7 | `context7` | `c7_` | T0_READ | nexi, operator | `npx @upstash/context7-mcp` (`CONTEXT7_API_KEY`) | 2 (live docs) | disabled |

**code-review-graph** — structure/impact tooling for the repo at
`/home/x-nch/xnchSystems`. Only read/introspection tools are allow-listed
(`query_graph_tool`, `semantic_search_nodes_tool`, `get_architecture_overview_tool`,
`get_impact_radius_tool`, `get_review_context_tool`, `get_affected_flows_tool`,
`list_communities_tool`, `get_community_tool`, `list_flows_tool`, `get_flow_tool`,
`detect_changes_tool`, `list_graph_stats_tool`, `get_knowledge_gaps_tool`,
`find_large_functions_tool`). Build/write tools are denied (`build_or_update_graph_tool`,
`run_postprocess_tool`, `embed_graph_tool`, `refactor_tool`, `apply_refactor_tool`).

**agentmemory** — cross-session agent memory behind `agentmemory.service` on gate7
(`:3111`), reached via the `npx @agentmemory/mcp` stdio proxy. 11 tools exposed
(recall/save/lesson/action/session/profile/frontier family). Destructive or
heavy ops are denied (`memory_governance_delete`, `memory_heal`, `memory_export`,
`memory_consolidate`, `memory_crystallize`, `memory_mesh_sync`,
`memory_obsidian_export`, `memory_snapshot_create`, `memory_compress_file`).

**docs-test** — local Context7-style docs (canned snippets for FastAPI, Pydantic,
MCP, LiteLLM, Kuzu). No API key. Tools: `resolve-library-id`, `query-docs`.

**context7** — live library docs. Disabled by default; enable in YAML and set
`CONTEXT7_API_KEY`. Tools appear as `c7_resolve-library-id`, `c7_query-docs`.

---

## Actor & tier model

Tool access is enforced by the same model used for native tools — no special path for
bridged tools.

Tool tiers (`xnch_mcp/tiers.py`):

| Tier | Level | Meaning |
|------|-------|---------|
| `T0_READ` | 0 | Read-only introspection |
| `T1_WRITE` | 1 | Writes to memory / stores |
| `T2_EXEC` | 2 | Command execution / side effects |

Trust levels map to a maximum tier (`xnch/security/trust_model.py` + `xnch_mcp/auth.py`):

| Trust level | Actors | Max tier |
|-------------|--------|----------|
| `UNTRUSTED` / `EXTERNAL_AGENT` | `external`, `viewer` | `T0_READ` |
| `TRUSTED_AGENT` | `opencode`, `agent`, `perception_daemon`, `consolidation_job` | `T1_WRITE` |
| `OWNER` | `operator`, `admin` | `T2_EXEC` |
| `SYSTEM` | `nexi` | `T2_EXEC` |

A tool is visible to an actor only when **both** hold:

- `tool.allowed_actors` includes the actor role, and
- `tool.tier <= max_tier_for_role(actor_role)`.

So a `T1_WRITE` bridged tool (e.g. `am_memory_save`) is hidden from `viewer`/`external`
even if the server config lists them, and `nexi` (SYSTEM) can use every bridged tool the
server exposes.

---

## Tool prefixing & audit

**Prefixing.** Each remote tool is re-registered as `{tool_prefix}{original_name}` and
its description is prefixed with `[{server_id}] `. Examples:

| Original (remote) | Prefixed (Nexi tool loop) |
|-------------------|---------------------------|
| `query_graph_tool` | `crg_query_graph_tool` |
| `memory_recall` | `am_memory_recall` |
| `resolve-library-id` | `doc_resolve-library-id` |

Prefixes avoid collisions between servers and make provenance obvious to the model. The
Nexi character prompt lists the three active groups (`crg_*`, `am_*`, `doc_*`) and a
`tool_routing` table.

**Audit.** `invoke_tool` records every call in the event log as `xnch.mcp` /
`TOOL_CALL`. Bridged calls add three provenance fields:

```json
{
  "tool": "crg_query_graph_tool",
  "actor": "nexi",
  "tier": "T0_READ",
  "duration_ms": 512,
  "bridge": true,
  "mcp_server": "code-review-graph",
  "original_tool": "query_graph_tool"
}
```

Native `xnch_*` calls omit `bridge`, `mcp_server`, and `original_tool`. Failed calls
emit `TOOL_CALL_FAILED` with the error string and same fields.

---

## Tool round bump (3 → 5)

The chat loop is capped at a number of model rounds to bound latency and token use.
The cap rises when the bridge is active because more capable tools usually mean more
round-trips before the model has enough ground truth to answer.

Precedence (`chat_tools.py:_max_tool_rounds`):

1. `XNCH_MCP_MAX_TOOL_ROUNDS` env var — explicit override.
2. Bridge active (`pool.started` **and** `pool.has_enabled_servers`) → `mcp_max_tool_rounds_with_bridge` (**5**).
3. Otherwise → `mcp_max_tool_rounds` (**3**).

Settings (`xnch/config.py`): `mcp_max_tool_rounds: int = 3`,
`mcp_max_tool_rounds_with_bridge: int = 5`.

---

## Lifecycle & health

**Startup** (`xnch/main.py` lifespan): if `mcp_bridge_enabled` (default `true`) and
`mcp_servers_path` (`~/.xnch/mcp-servers.yaml`) exists, `McpBridgePool.from_path` is
built, `await bridge.start()` connects every enabled server, and the pool is installed
via `set_bridge_pool`. Shutdown stops all clients and clears the global.

**Per-server supervisor** (`bridge/client.py`): each `McpServerClient` runs a
supervisor task (`mcp-bridge-{server_id}`) that owns one stdio subprocess and MCP
`ClientSession`. It blocks until initialized, then serves calls under an asyncio lock.
A crashed child is logged; the pool continues with the remaining servers (startup
failure of one server does not take down the bridge).

**Status:**

- `GET /mcp/servers` → `McpBridgePool.server_status()` rows: `server_id`, `enabled`,
  `connected`, `tool_prefix`, `tool_count`, `actors`, `tier`.
- `xnch_health` → includes an `mcp_bridge` summary (`enabled`, `servers`).

---

## Nexi character integration

`nexi/character/` splits persona config into three YAML files:

- `persona.yaml` — identity, communication style, `never_do` rules
- `capabilities.yaml` — hosts, filesystem, tool inventory, `tool_routing`
- `identity_facts.yaml` — canonical facts seeded to pgvector

How the model should use bridged tools:

- `capabilities.summary` names the bridged groups (`crg_*`, `am_*`, `doc_*`) and notes
  the 5-round cap when the bridge is active. Chat prompts include this summary only;
  `GET /nexi/capabilities` returns the full document.
- `tools.code_graph` — `crg_*` for structure/callers/tests/impact.
- `tools.agent_memory` — `am_*` for cross-session notes, lessons, actions.
- `tools.library_docs` — `doc_*` (offline) / `c7_*` (live, when enabled).
- `tool_routing` maps intent → tool family, e.g. "Code structure / callers / tests? →
  `crg_*`", "Cross-session agent notes / lessons / actions? → `am_memory_*`".

---

## See also

- [MCP bridge deploy runbook](../runbooks/mcp-bridge-deploy.md) — deploy, restart, verification
- [Web search deploy runbook](../runbooks/web-search-deploy.md) — SearXNG + `xnch_web_search`
- [MCP HTTP API reference](../reference/mcp-http-api.md) — `GET /mcp/tools`, `POST /mcp/call`, `GET /mcp/servers`
- [MCP tools catalog](../reference/mcp-tools.md) — native + bridged tool matrix
- Diagram: [`docs/diagrams/mcp-bridge.mmd`](../diagrams/mcp-bridge.mmd)
- Handoff: [`misc/opencode/xnch-mcp-handoff.md`](../../misc/opencode/xnch-mcp-handoff.md)
- [Reference index](../reference/index.md) — MCP tools, HTTP API, config
- [Memory routing guide](memory-routing.md) — episodic vs agentmemory
- [Memory routing deploy](../runbooks/memory-routing-deploy.md)
- Legacy notes: [`misc/notes/nexi-mcp-bridge.md`](../../misc/notes/nexi-mcp-bridge.md)
