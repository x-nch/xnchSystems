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