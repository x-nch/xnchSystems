# MCP Tools Catalog — xnch

Complete catalog of tools exposed through `xnch_mcp` on gate7 (`xnch :8001`).
Tools are consumed two ways:

- **Nexi runtime** — via the bridge + native tools in the `POST /nexi/chat` tool loop
  (actor `nexi`). See [mcp-bridge architecture](../architecture/mcp-bridge.md).
- **OpenCode / Cursor** — direct stdio MCP (`python -m xnch_mcp` with
  `XNCH_ACTOR=opencode` in `opencode.jsonc`), which proxies to the same HTTP endpoints.
  OpenCode sees **native tools only** — bridged servers are not exposed to non-`nexi`/`operator`
  actors.

Source of truth: `xnch_mcp/handlers/`, `xnch_mcp/registry.py`, `xnch_mcp/bridge/pool.py`.

## Contents

- [Tiers & actor model](#tiers--actor-model)
- [Dual memory systems](#dual-memory-systems)
- [Native tools](#native-tools)
- [Bridged prefixes](#bridged-prefixes)
- [xnch_web_search](#xnch_web_search)
- [Actor matrix](#actor-matrix)
- [Tool routing decision matrix](#tool-routing-decision-matrix)
- [Index note](#index-note)

---

## Tiers & actor model

Tiers (`xnch_mcp/tiers.py`): `T0_READ` (0), `T1_WRITE` (1), `T2_EXEC` (2).

Each actor maps to a maximum tier via trust level (`xnch/security/trust_model.py`,
`xnch_mcp/auth.py`):

| Actor | Trust level | Max tier |
|-------|-------------|----------|
| `nexi` | SYSTEM | T2_EXEC |
| `operator`, `admin` | OWNER | T2_EXEC |
| `opencode`, `agent`, `perception_daemon`, `consolidation_job` | TRUSTED_AGENT | T1_WRITE |
| `viewer` | EXTERNAL_AGENT | T0_READ |
| `external` | UNTRUSTED | T0_READ |

A tool is visible to an actor when the actor is in the tool's `allowed_actors` (if set)
**and** the tool tier ≤ the actor's max tier.

---

## Dual memory systems

Nexi uses two **independent** stores. See [memory-routing guide](../guides/memory-routing.md).

| Family | Backend | Auto in chat? | `memory_target` audit |
|--------|---------|---------------|----------------------|
| `xnch_memory_*` | Postgres pgvector | Yes (recall + post-turn store) | `episodic` |
| `am_memory_*` | agentmemory `:3111` | No (optional prefetch) | `agentmemory` |

`xnch_memory_store_note` is **blocked for actor `nexi`** (HTTP 403). Nexi must use
`am_memory_save` or `am_memory_lesson_save` for curated facts.

---

## Native tools

All native tools are defined in `xnch_mcp/handlers/`. `allowed_actors = *` means no
restriction beyond the tier check.

| Tool | Tier | Allowed actors | Purpose |
|------|------|----------------|---------|
| `xnch_health` | T0_READ | all | Service health + Redis connectivity, includes `mcp_bridge` and `web_search` blocks |
| `xnch_status` | T0_READ | all | `system_state_version` and `policy_version` |
| `xnch_memory_recall` | T0_READ | all | Episodic/pgvector search — chat continuity (“what did we discuss?”) |
| `xnch_memory_surface` | T0_READ | all | List pending proactivity events |
| `xnch_memory_store_note` | T1_WRITE | T1+ except **nexi blocked** | Manual pgvector note — operator/opencode only; nexi → 403 |
| `xnch_session_run` | T2_EXEC | T2 (owner/system) | Run governed decision pipeline (`/session/init`) for an intent |
| `xnch_fs_list` | T0_READ | `nexi`, `operator`, `admin` | List files/dirs on node-a or node-b |
| `xnch_fs_read` | T0_READ | `nexi`, `operator`, `admin` | Read a file on node-a or node-b (offset/max_bytes) |
| `xnch_fs_stat` | T0_READ | `nexi`, `operator`, `admin` | File/dir metadata on node-a or node-b |
| `xnch_fs_exists` | T0_READ | `nexi`, `operator`, `admin` | Check path existence on node-a or node-b |
| `xnch_fs_glob` | T0_READ | `nexi`, `operator`, `admin` | Glob files under allowed roots |
| `xnch_exec_run` | T2_EXEC | `nexi`, `operator`, `admin` | Run an allowlisted shell command (see exec-policy.yaml) |
| `xnch_web_search` | T0_READ | `nexi`, `operator` | Anonymous web search via self-hosted SearXNG |

Total: **13 native tools**.

---

## Bridged prefixes

Bridged servers are declared in `~/.xnch/mcp-servers.yaml` and spawned as stdio
subprocesses by `xnch_mcp.bridge`. Tools are re-registered as
`{prefix}{original_name}` with the server's tier and actor list. Only `nexi` and
`operator` are enabled actors. See [mcp-bridge architecture](../architecture/mcp-bridge.md) for the request flow.

| Server | Prefix | Tier | Actors | Example tools |
|--------|--------|------|--------|---------------|
| code-review-graph | `crg_` | T0_READ | nexi, operator | `crg_query_graph_tool`, `crg_detect_changes_tool`, `crg_semantic_search_nodes_tool` |
| agentmemory | `am_` | T1_WRITE | nexi, operator | `am_memory_lesson_save`, `am_memory_lesson_recall`, `am_memory_save`, `am_memory_action_*` |
| docs-test | `doc_` | T0_READ | nexi, operator | `doc_resolve-library-id`, `doc_query-docs` |
| context7 | `c7_` | T0_READ | nexi, operator | `c7_resolve-library-id`, `c7_query-docs` (**disabled** by default) |

Example calls (actor `nexi`):

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"crg_list_graph_stats_tool","arguments":{}}'
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"am_memory_recall","arguments":{"query":"MCP bridge","limit":3}}'
```

---

## xnch_web_search

- **Tier:** T0_READ
- **Actors:** `nexi`, `operator` (enforced twice: tool `allowed_actors` and
  `web-search.yaml` `allowed_actors`)
- **Backend:** self-hosted SearXNG on gate7 (`http://127.0.0.1:8888`), anonymous
  metasearch across configured engines (duckduckgo, brave, wikipedia). No commercial API.

Inputs:

| Field | Type | Notes |
|-------|------|-------|
| `query` | string (required) | Specific query; avoid secrets in query text |
| `limit` | int (1–10) | Max results; capped at policy `max_results_cap` |
| `categories` | string | Optional SearXNG category, e.g. `general`, `it` |

Use for current events, CVEs, release notes, and external docs not in the repo.
Prefer `crg_*` for code structure and `doc_*` for offline library snippets.

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_web_search","arguments":{"query":"CVE-2026 LiteLLM proxy","limit":3}}'
```

---

## Actor matrix

Which tools each actor can call. ✓ = visible, — = blocked (by tier or `allowed_actors`).

| Tool family | nexi | operator | admin | opencode | agent | viewer | external |
|-------------|:----:|:--------:|:-----:|:--------:|:-----:|:------:|:--------:|
| `xnch_health` / `xnch_status` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `xnch_memory_recall` / `xnch_memory_surface` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `xnch_memory_store_note` | **403** | ✓ | ✓ | ✓ | ✓ | — | — |
| `xnch_session_run` | ✓ | ✓ | ✓ | — | — | — | — |
| `xnch_fs_*` (5 tools) | ✓ | ✓ | ✓ | — | — | — | — |
| `xnch_exec_run` | ✓ | ✓ | ✓ | — | — | — | — |
| `xnch_web_search` | ✓ | ✓ | — | — | — | — | — |
| `crg_*` / `am_*` / `doc_*` (bridged) | ✓ | ✓ | — | — | — | — | — |

Notes:

- `nexi` is blocked from `xnch_memory_store_note` by memory routing policy (not tier).
  Use `am_memory_*` for curated writes.
- `admin` is `OWNER` (T2_EXEC) and has full native access, but is not in the bridged
  server actor lists, so it sees no `crg_*`/`am_*`/`doc_*` tools.
- `opencode`/`agent` are `TRUSTED_AGENT` (max T1_WRITE): read + note tools, no
  session/fs/exec/web, no bridged tools.

---

## Tool routing decision matrix

From `nexi/character/capabilities.yaml` `tool_routing` — which tool family to reach
for which need.

| Need | Tool family | Example |
|------|-------------|---------|
| Code structure / callers / callees / tests / impact | `crg_*` | `crg_query_graph_tool` |
| Find functions/classes by keyword | `crg_*` | `crg_semantic_search_nodes_tool` |
| Risk-scored code change analysis | `crg_*` | `crg_detect_changes_tool` |
| File contents on disk (both hosts) | `xnch_fs_*` | `xnch_fs_read` |
| Live service state (status/logs/health probes) | `xnch_exec_run` | `journalctl`, `systemctl status` |
| What did we discuss? / chat episodic recall | `xnch_memory_*` | `xnch_memory_recall` |
| Save deploy lesson / architecture fact | `am_memory_*` | `am_memory_lesson_save` |
| Recall deploy lessons | `am_memory_*` | `am_memory_lesson_recall` |
| Cross-session agent notes / actions | `am_memory_*` | `am_memory_recall`, `am_memory_action_*` |
| Current events / external docs / CVEs | `xnch_web_search` | `query="CVE ..."` |
| Library/framework API docs (offline) | `doc_*` | `doc_query-docs` |
| Library/framework API docs (live) | `c7_*` | `c7_resolve-library-id` (when enabled) |
| Governed decision pipeline / action | `xnch_session_run` | intent or command |

---

## Index note

See [index.md](index.md) for the full reference index.
