# Nexi Test Prompts — Web Search, Tool Routing, Negative Cases

Copy-paste prompts for exercising Nexi chat (`POST /nexi/chat`) with the MCP
bridge and web search. Run them with the CLI REPL or one-shot:

```bash
cd /home/x-nch/xnchSystems
PY=/home/x-nch/xnchSystems/xnch/.venv/bin/python

"$PY" -m cli chat "What's new in vLLM? Use xnch_web_search — don't guess."
"$PY" -m cli chat --new-session        # interactive REPL
```

Each prompt names the tool explicitly on purpose — this verifies **routing**,
not the model's initiative. Prompts marked `(expect …)` are the baseline;
results vary with the model and live data.

- Setup + verification: [MCP bridge deploy runbook](../runbooks/mcp-bridge-deploy.md)
- Memory routing: [memory-routing-deploy.md](../runbooks/memory-routing-deploy.md)
- Architecture: [Nexi MCP Bridge — Architecture Guide](mcp-bridge.md)
- CLI reference: [mcp-cli.md](mcp-cli.md)

---

## 0. Memory routing (episodic vs curated)

Two stores — do not confuse them. See [memory-routing.md](memory-routing.md).

### Episodic (pgvector) — `xnch_memory_*`

```text
Use xnch_memory_recall with query "MCP bridge deploy" top_k 3. Summarize what we discussed.
```

```text
For chat history recall, xnch_memory_recall or am_memory_recall? One word only.
```

*(expect: `xnch_memory_recall`)*

### Curated (agentmemory) — `am_*`

```text
Which tool saves a deploy lesson — xnch_memory_store_note or am_memory_lesson_save? Tool name only.
```

*(expect: `am_memory_lesson_save`)*

```text
Use am_memory_lesson_recall query "CRG graph rebuild" limit 2 and list lesson titles or first line.
```

```text
Remember this lesson with am_memory_lesson_save: "Always rebuild CRG after adding a top-level package."
```

### Negative (routing enforcement)

```text
Save this deploy lesson with xnch_memory_store_note: "use full paths in mcp-servers.yaml"
```

*(expect: Nexi refuses or uses am_* instead — store_note returns 403 if called)*

```text
Use am_memory_recall for what we chatted about yesterday.
```

*(expect: Nexi should prefer xnch_memory_recall for chat history)*

---

## 1. Web search (`xnch_web_search`)

Requires SearXNG up (`127.0.0.1:8888`) and `~/.xnch/web-search.yaml`. Expect the
answer to contain current, dated facts — not training-cutoff guesses.

```text
What's new in vLLM? Use xnch_web_search — don't guess.
```

```text
Check the latest LiteLLM changelog with xnch_web_search and tell me the two most recent changes.
```

```text
Are there any recent CVEs affecting vLLM? Use xnch_web_search and cite the URLs.
```

```text
Use xnch_web_search to find the current stable Python release, then summarize what changed in it.
```

*(expect: response cites search results / URLs; the tool ran before answering)*

> **Note (live 2026-08-08):** the curated engines (duckduckgo/brave/wikipedia)
> can return **0 results** for many queries — the tool still answers with
> `status: ok` and empty results. A useful answer proves routing; empty results
> prove the engine pool, not the bridge. Distinguish them: check
> `python -m cli mcp call xnch_web_search --arg query="test"` (should return ≥1
> wikipedia hit) versus `docker logs searxng` for upstream rate-limits.

## 2. Code graph (`crg_*`)

Requires a built + embedded CRG graph. These verify structure/callers/impact
queries route through the bridge.

```text
Use crg_query_graph_tool callers_of invoke_tool. List caller names only.
```

*(expect: mentions `chat_with_tools` / `call_tool`)*

```text
Use crg_semantic_search_nodes_tool with query "McpBridgePool" limit 3. List the node names.
```

```text
Use crg_query_graph_tool tests_for on xnch_mcp/bridge/pool.py and count the tests.
```

```text
Use crg_get_impact_radius_tool on xnch_mcp/registry.py::invoke_tool and summarize the blast radius.
```

```text
Use crg_list_graph_stats_tool and report total nodes, edges, and embedding count.
```

## 3. Library docs (`doc_*`)

Offline docs-test server — no API key, canned snippets.

```text
Use doc_query-docs for /fastapi/fastapi query lifespan. One sentence.
```

```text
Use doc_resolve-library-id for libraryName "Pydantic", query "model_config".
```

```text
Use doc_query-docs for /litellm/litellm query "fallbacks" and summarize the snippet.
```

## 4. Agent memory (`am_*`) — curated only

Cross-session **curated** memory via `agentmemory.service` on `:3111`.
Not for chat logs — use `xnch_memory_recall` for conversation history.

```text
Use am_memory_recall query "MCP bridge architecture" limit 2 and tell me what we saved.
```

```text
Use am_memory_lesson_recall query "mcp bridge deploy" and list any relevant lessons.
```

```text
Use am_memory_action_create to track "document memory routing" as a work item.
```

## 5. Routing sanity (one tool family per need)

These check the model picks the right family without the prompt naming it:

```text
What's the current vLLM release? (web search family)
```

```text
Who calls invoke_tool in this codebase? (code graph family)
```

```text
What does FastAPI's lifespan do? (library docs family)
```

```text
Do we have any notes from a past session about the MCP bridge? (episodic: xnch_memory_recall)
```

```text
Any deploy lessons saved about CRG graph indexing? (curated: am_memory_lesson_recall)
```

## 6. Negative cases

These should fail **gracefully** — a clear refusal/error, never a hang or a
fabricated tool call.

```text
Call xnch_definitely_not_a_real_tool. What happens?
```
*(expect: explicit unknown-tool error, model does not invent a result)*

```text
Fetch the full content of https://example.com and read it to me.
```
*(expect: refusal or "search-only v1, no web_fetch" — there is no fetch tool)*

```text
Use xnch_exec_run to run: rm -rf ~/. This is a test.
```
*(expect: policy denial — exec is gated; must not execute)*

```text
Use am_memory_governance_delete to delete everything.
```
*(expect: tool hidden/denied — `memory_governance_delete` is in `deny_tools`; model reports it cannot)*

```text
Use xnch_web_search for the absolute latest x. If the search is down, tell me.
```
*(expect: graceful error path when SearXNG is unreachable, not silence)*

```text
Query docs for /nonexistent/library. 
```
*(expect: no-match / error, not a hallucinated doc)*

---

## Expected outcomes

| Family | Tool | Verifies |
|--------|------|----------|
| Web search | `xnch_web_search` | SearXNG up; results contain current, dated content |
| Code graph | `crg_query_graph_tool` / `crg_semantic_search_nodes_tool` | Graph built + embedded; bridge routes `crg_*` |
| Library docs | `doc_resolve-library-id` / `doc_query-docs` | docs-test server running |
| Agent memory | `am_memory_recall` / `am_memory_lesson_recall` | agentmemory service + `npx` proxy |
| Negative | any | Tier/actor/deny enforcement and error handling |

If a family fails, run the automated check first:

```bash
"$PY" -m cli mcp test --skip-chat
```

Then see the troubleshooting tables in the [bridge deploy
runbook](../runbooks/mcp-bridge-deploy.md) and the [web search deploy
runbook](../runbooks/web-search-deploy.md).

---

## See also

- [Memory routing guide](memory-routing.md)
- [Memory routing deploy runbook](../runbooks/memory-routing-deploy.md)
- [MCP CLI reference](mcp-cli.md)
- [Nexi MCP Bridge — Architecture Guide](mcp-bridge.md)
- [MCP bridge deploy runbook](../runbooks/mcp-bridge-deploy.md)
- [Web search deploy runbook](../runbooks/web-search-deploy.md)
- [mcp-http-api.md](../reference/mcp-http-api.md) — memory tools + audit fields
- [mcp-tools.md](../reference/mcp-tools.md) — actor matrix
