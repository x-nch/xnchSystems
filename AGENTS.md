## Multi-Repo Structure

- `xnch/` — git submodule → github.com/x-nch/xnch (control plane API: REST routes, auth, memory, policy, learning)
- `nexi/` — git submodule → github.com/x-nch/nexi (execution engine: FastAPI, decision/policy pipeline)
- `infra/` — k3s manifests, Docker, systemd, mem0, zep
- `docs/` — Architecture docs, runbooks, diagrams
- `scripts/` — Helper scripts, migration agent
- `misc/` — Historical records, conversations, reports
- Root `pyproject.toml` requires Python 3.13+ (packages specify `>=3.11`, align to 3.13)

**Entrypoints:**
- `nexi/main.py` — Engine CLI (inside submodule)
- `xnch/main.py` — API server (inside submodule)

## Developer Commands

```bash
git submodule update --init --recursive  # Clone submodules
pytest                              # Run all tests (auto-asyncio)
pytest nexi/tests                   # Run only nexi tests
pytest xnch/tests                   # Run only xnch tests
pytest tests                        # Run e2e tests
pytest nexi/tests/test_evaluator.py # Run single test file
pytest -k "test_auth"               # Run tests matching keyword
pytest -k "not auth" --tb=short     # Run except auth tests
pytest --cov=nexi --cov=xnch        # Coverage report
pytest -x --no-header               # Fail-fast, no header
```

`pytest.ini_options` sets `asyncio_mode = "auto"` globally — all tests run async.
Dev deps: `pytest`, `pytest-asyncio`, `httpx`, `fakeredis` (xnch).

## MCP Tools: code-review-graph

**ALWAYS use code-review-graph MCP tools BEFORE Grep/Glob/Read.**

| Tool | Use when |
|------|----------|
| `detect_changes` | Code review — risk-scored analysis |
| `get_impact_radius` | Understanding blast radius |
| `query_graph` | Finding callers, callees, tests |
| `semantic_search_nodes` | Finding code by keyword |
| `list_flows` / `get_flow` | Understanding execution paths |
| `list_communities` / `get_community` | Architecture overview |
| `get_architecture_overview` | High-level structure |
| `refactor` (rename/dead_code/suggest) | Code cleanup |
| `find_large_functions` | Size audits |
| `get_knowledge_gaps` | Structural weaknesses |
| `get_surprising_connections` | Unexpected coupling |

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

## Code Conventions

### Imports

```python
# stdlib first
import asyncio
from typing import Annotated
from uuid import uuid4
from pathlib import Path

# third-party
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# local relative imports (no absolute imports)
from .models import SessionContext
from ..config import settings
from ..utils.audit import emit_event
```

Do NOT import from sibling packages with absolute paths (e.g. `from xnch.X import Y`).

### Types & Annotations

- Use modern union syntax: `str | None`, not `Optional[str]`.
- Use `Annotated[T, Field(...)]` for constrained fields.
- Annotate ALL function signatures: both parameters and return types.
- Annotate module-level vars: `_xnch: XnchClient | None = None`.
- Use `list[Item]`, `dict[str, int]` (lowercase generics), not `List[Item]`.

### Naming

| Entity | Convention | Example |
|--------|-----------|---------|
| Classes | PascalCase | `SessionContext`, `PolicyFilter` |
| Enums | PascalCase; values are UPPERCASE | `IntentClass.EXECUTION` |
| Functions | snake_case | `select_decision`, `load_context` |
| Module-level consts | UPPER_SNAKE_CASE | `_DEFAULT_WEIGHTS` |
| Private helpers | `_snake_case` | `_make_session()` |
| Pydantic fields | snake_case (auto-mapped) | `session_id`, `target_entity_id` |

### Data Models

- Use **Pydantic `BaseModel`** for all request/response/data types.
- Use **`StrEnum`** for fixed-choice types (not `Enum` or bare `str`).
- Use `Field(default_factory=...)` for mutable defaults.
- Use `model_dump(mode="json")` for serialization when sending over HTTP.
- Use `model_validate(resp.json())` for deserialization from HTTP.
- Keep models in `models/` subpackages (e.g., `models/intent.py`, `models/session.py`).
- Re-export from `models/__init__.py` with explicit `__all__`.

### Error Handling

- Define custom exceptions for domain errors:
  ```python
  class TokenExpired(Exception): pass
  class ClarificationRequired(Exception): pass
  class PlanCompilationError(Exception): pass
  class AllOptionsBlocked(Exception): pass
  ```
- Catch specific exceptions (e.g., `httpx.ConnectError`), not bare `except`.
- Log warnings for non-fatal failures; use fire-and-forget for audit emission.
- HTTP responses: use `resp.raise_for_status()` after checking status codes.

### Configuration

- Use **Pydantic `BaseSettings`** with `env_prefix` and `env_file=".env"`.
- Prefix env vars: `NEXI_*` for nexi, `XNCH_*` for xnch.
- Use `Path` objects for filesystem paths; call `.expanduser()` and `.mkdir(parents=True, exist_ok=True)` when needed.
- Declare settings in `config.py` per package.

### Architecture

- **Pipeline pattern**: `intent_interpreter` → `load_context` → `generate_options` → `PolicyFilter` → `Evaluator` → `select_decision` → `compile_action_spec` → `dispatch_execution`.
- **Adapter pattern**: External services behind adapter classes (`XnchClient`, `ModelAdapter`).
- **FastAPI lifespan**: Use `@asynccontextmanager` for async startup/shutdown.
- **Store pattern**: Separate persistence from business logic (`EpisodicStore`, `GraphStore`, `RelationshipStore`).
- Use `logging.getLogger(__name__)` for loggers.

### Tests

- Place tests next to source: `nexi/tests/`, `xnch/tests/`, or `tests/` for e2e.
- Use helper functions prefixed `_make_*` to build test data.
- Use `conftest.py` for shared fixtures.
- Test files have module docstrings describing what they test.
- Fixtures marked `@pytest.fixture(autouse=True)` for isolation.

### File Organization

```
<package>/
  <package>/
    __init__.py          # Re-exports with __all__
    main.py              # FastAPI app entrypoint
    config.py            # Pydantic BaseSettings
    models/              # Data models (sub-packages)
      __init__.py
      intent.py
      session.py
      options.py
      ...
    pipeline/            # Processing pipeline (sub-package)
      __init__.py
      intent_interpreter.py
      evaluator.py
      ...
    adapters/            # External service clients
    utils/               # Shared helpers
    character/
    policies/
  tests/
    conftest.py
    test_*.py
```

## AI Agent Config Files

- `.cursorrules` — Contains MCP tool reference (see above section).
- `.claude/` — Claude-specific instructions.
- `opencode.jsonc` / `.opencode.json` — Opencode config.

## Skill Scope

Engineering-only. Marketing/SEO/growth skills (global `~/.agents/skills`,
`~/.claude/skills`) are out of scope for this repo — see
`.opencode/rules/skills-scope.md`. Use the `review-loop` skill + `reviewer` agent
for code review.
