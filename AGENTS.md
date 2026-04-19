## Monorepo Structure

- `nexi/` — Execution engine (Python 3.11+, FastAPI, decision/policy system)
- `xnch/` — Control plane API (Python 3.13+, REST routes, auth, memory)
- Root pyproject.toml requires Python 3.13+

**Entrypoints:**
- `nexi/nexi/main.py` — Engine CLI
- `xnch/xnch/main.py` — API server

## Developer Commands

```bash
pytest                  # Run all tests (auto-asyncio mode)
pytest nexi/tests       # Run only nexi tests
pytest xnch/tests     # Run only xnch tests
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