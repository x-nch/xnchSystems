## Monorepo Structure

- `nexi/` — Execution engine (FastAPI, decision/policy system)
- `xnch/` — Control plane API (REST routes, auth, memory)
- Root pyproject.toml requires Python 3.13+

**Note:** Individual packages specify `>=3.11` but root requires `>=3.13`. Align to 3.13.

**Entrypoints:**
- `nexi/nexi/main.py` — Engine CLI
- `xnch/xnch/main.py` — API server

## Developer Commands

```bash
pytest                  # Run all tests (auto-asyncio mode)
pytest nexi/tests       # Run only nexi tests
pytest xnch/tests     # Run only xnch tests
pytest nexi/tests/test_evaluator.py  # Run single test file
```

No dedicated lint/typecheck commands in this repo.

## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. Use graph tools BEFORE Grep/Glob.**

| Tool | Use when |
|------|----------|
| `detect_changes` | Code review — risk-scored analysis |
| `get_impact_radius` | Understanding blast radius |
| `query_graph` | Finding callers, callees, tests |

Workflow: `detect_changes` → `get_review_context` → check coverage.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
