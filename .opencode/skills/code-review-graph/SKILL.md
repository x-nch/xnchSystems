---
name: code-review-graph
description: Use when reviewing code changes in this repo, tracing impact, or finding untested hotspots. Documents the code-review-graph MCP tools available in the opencode session.
---

# code-review-graph

This repo runs a `code-review-graph` MCP server. Use it BEFORE grep/glob for
code-review and impact analysis.

## Key tools (already available as MCP tools in-session)
- `detect_changes` — risk-scored review of the current diff. Read-only.
  `uvx code-review-graph detect-changes --repo . --base <merge-base>`
- `get_impact_radius` — blast radius of changed files.
- `query_graph` patterns: callers_of, callees_of, tests_for, importers_of.
- `semantic_search_nodes` — find code by description (after `embed_graph`).
- `get_knowledge_gaps` — untested hotspots, isolated nodes.
- `build_or_update_graph_tool` / `run_postprocess_tool` — refresh the graph.

## Workflow
1. `detect_changes` on the diff (default base HEAD~1).
2. For each high-risk item, `get_impact_radius` + `query_graph tests_for`.
3. Route fixes to subagents; verify with pytest.
4. Re-run `detect_changes` to confirm zero high-risk items.
