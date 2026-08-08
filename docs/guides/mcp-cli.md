# MCP CLI Reference — `python -m cli mcp`

The `mcp` subcommand group of the xnch CLI drives the MCP bridge over HTTP. It
talks to `xnch :8001` (`/mcp/servers`, `/mcp/tools`, `/mcp/call`) as an actor, so
it needs the xnch API up — not the LLM path.

- Deploy + verification: [MCP bridge deploy runbook](../runbooks/mcp-bridge-deploy.md)
- Architecture: [Nexi MCP Bridge — Architecture Guide](mcp-bridge.md)
- API reference: [`docs/reference/mcp-http-api.md`](../reference/mcp-http-api.md)

---

## Setup

Run from the repo root with the repo venv (the `cli` package lives at repo root
and imports `xnch.routing`):

```bash
cd /home/x-nch/xnchSystems
PY=/home/x-nch/xnchSystems/xnch/.venv/bin/python

"$PY" -m cli mcp --help
```

Environment (`cli/config.py`):

| Var | Default | Meaning |
|-----|---------|---------|
| `XNCH_BASE_URL` | `http://localhost:8001` | xnch API base |
| `NEXI_BASE_URL` | `http://localhost:8000` | nexi engine base |
| `XNCH_ACTOR` | `operator` | Actor used by `chat` / general commands |
| `XNCH_AUTH_TOKEN` | — | Bearer token (overrides minted JWT) |
| `XNCH_AUTH_SECRET` | — | HS256 secret for auto-minting a token |

The `mcp` subcommands default to `--actor nexi` explicitly, so they work with no
env beyond `XNCH_BASE_URL` pointing at the API.

Every `mcp` subcommand accepts:

| Flag | Meaning |
|------|---------|
| `-a / --actor <role>` | `X-Actor-Role` header (default `nexi`) |
| `--json` | Print raw JSON instead of the human summary |

---

## `mcp servers`

List bridge server status.

```bash
"$PY" -m cli mcp servers
# code-review-graph: connected  tools=14  prefix=crg_
# agentmemory: connected  tools=11  prefix=am_
# docs-test: connected  tools=2  prefix=doc_
# context7: down  tools=0  prefix=c7_
```

```bash
"$PY" -m cli mcp servers --json
```

A server is `down` when its stdio subprocess failed to connect. The pool keeps
running with whatever connected — see the deploy runbook's troubleshooting
section. If the bridge is disabled the command prints `MCP bridge disabled`.

## `mcp tools`

List the tools visible to an actor, optionally filtered by prefix.

```bash
"$PY" -m cli mcp tools --actor nexi
# actor: nexi  tools: 40
#   xnch_health  [T0_READ]
#   ...

"$PY" -m cli mcp tools --actor nexi --prefix crg_    # bridged CRG tools only
"$PY" -m cli mcp tools --actor nexi --prefix xnch_   # native tools only (13)
```

**Expected counts (live):** `nexi` sees **40** tools = 13 native (`xnch_*`) + 27
bridged (`crg_*` 14, `am_*` 11, `doc_*` 2). `operator` sees the same set;
`viewer`/`external` see read-only tools only (T1_WRITE tools like `am_*` are
hidden — actor/tier model in the architecture guide).

## `mcp call`

Invoke any tool visible to the actor.

```bash
"$PY" -m cli mcp call crg_list_graph_stats_tool
"$PY" -m cli mcp call am_memory_recall --arg query="MCP bridge" --arg limit=2
"$PY" -m cli mcp call xnch_web_search --arg query="vLLM latest release" --arg limit=3
"$PY" -m cli mcp call xnch_health --json
```

Argument syntax:

- `--arg key=value` — repeatable; `value` is parsed as JSON when possible, else
  taken as a string:
  - `--arg query="MCP bridge"` → string
  - `--arg limit=2` → integer
  - `--arg args='{"a": 1}'` → object
- No `--arg` at all → `{}`.
- Unknown tool → HTTP error with the bridge's message (`Unknown bridged tool: ...`).
- Tool denied for the actor → permission error from `/mcp/call`.

Human output pretty-prints dict/list results; `--json` always emits the raw
payload (useful for piping to `jq`).

## `mcp test`

Run the bridge integration suite.

```bash
"$PY" -m cli mcp test --skip-chat     # 11 tool-level cases; no LLM needed
"$PY" -m cli mcp test                 # + 2 live /nexi/chat tool-loop cases (needs LiteLLM/Ornith)
"$PY" -m cli mcp test --skip-chat --json
```

Coverage (from `cli/mcp_tests.py`):

| Case | Checks |
|------|--------|
| `bridge servers` | ≥ 3 connected servers for `nexi` |
| `tool count` | ≥ 35 tools for `nexi` |
| `xnch_health` | `mcp_bridge.enabled == true` |
| `crg_list_graph_stats` | CRG `status: ok` |
| `crg_semantic_search` | embeddings present (graph must be built + embedded) |
| `crg_callers_invoke_tool` | `chat_with_tools` is a caller of `invoke_tool` (fails on a stale graph — see runbook troubleshooting) |
| `am_memory_recall` | agentmemory returns results |
| `doc_resolve_library` / `doc_query_docs` | offline docs match + query |
| `xnch_web_search` / `web_search_health` | SearXNG backend up, web search enabled |

**Exit codes:** `0` when every case passes; `1` when any case fails. With
`--json` the summary is `{"passed": N, "failed": M, "results": [...]}`.

---

## Memory routing verify

```bash
# nexi blocked from store_note (403)
"$PY" -m cli mcp call xnch_memory_store_note --arg text="x" --actor nexi

# episodic + curated recall
"$PY" -m cli mcp call xnch_memory_recall --arg query="deploy" --arg top_k=2
"$PY" -m cli mcp call am_memory_lesson_recall --arg query="CRG" --arg limit=2
```

Full runbook: [memory-routing-deploy.md](../runbooks/memory-routing-deploy.md).

---

## Related curl endpoints

The CLI is a thin wrapper over these (actor header `X-Actor-Role`):

```bash
curl -s http://127.0.0.1:8001/mcp/servers -H 'X-Actor-Role: nexi' | jq .
curl -s http://127.0.0.1:8001/mcp/tools -H 'X-Actor-Role: nexi' | jq '.tools[].name'
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"crg_list_graph_stats_tool","arguments":{}}'
```

The bridge also exposes the OpenAI-format tool list at `GET /mcp/tools/openai`
(documented in [mcp-http-api.md](../reference/mcp-http-api.md)).

---

## See also

- [MCP bridge deploy runbook](../runbooks/mcp-bridge-deploy.md)
- [Web search deploy runbook](../runbooks/web-search-deploy.md)
- [Memory routing deploy runbook](../runbooks/memory-routing-deploy.md)
- [Memory routing guide](memory-routing.md)
- [Nexi test prompts](nexi-test-prompts.md)
- API reference: [`docs/reference/mcp-http-api.md`](../reference/mcp-http-api.md)
