# OpenCode handoff: xnch CLI

Copy everything below the line into a new OpenCode session.

---

## Task

Continue development of the **xnch CLI** in `/home/x-nch/xnchSystems`. This is a Typer-based client for the xnch control plane (gate7 / Node A). Read `AGENTS.md` for repo conventions. Use the `code-review-graph` MCP tools before Grep/Glob/Read when exploring.

## What already exists

Package: `cli/` at repo root.

```
cli/
  __init__.py
  __main__.py      # python -m cli
  main.py          # Typer app + commands
  client.py        # httpx sync client (XnchCliClient)
  config.py        # env: XNCH_BASE_URL, XNCH_AUTH_SECRET, XNCH_AUTH_TOKEN, XNCH_ACTOR, NEXI_BASE_URL
  util.py          # join_args(), dedupe_memory_results()
tests/
  test_cli.py
  test_cli_util.py
```

Entry point in root `pyproject.toml`:
```toml
[project.scripts]
xnch-cli = "cli.main:app"
```

### Commands shipped

| Command | API | Notes |
|---------|-----|-------|
| `health [--nexi]` | GET `/health` | |
| `status` | GET `/system/state` | |
| `run <words...>` | POST `/session/init` | Multi-word via `join_args` |
| `chat [words...]` | POST `/nexi/chat` | REPL if no message; `--stream`, `--session` |
| `auth token` | local JWT mint | needs `XNCH_AUTH_SECRET` |
| `memory recall <words...>` | POST `/nexi/memory/recall` | `--unique` default, `--all` for dupes |
| `memory surface` | GET `/nexi/memory/surface` | |

### Run / verify

```bash
cd /home/x-nch/xnchSystems
source .venv/bin/activate
python -m cli --help
pytest tests/test_cli.py tests/test_cli_util.py -q
python -m cli health
```

Default xnch: `http://localhost:8001`. Dev auth: `actor:operator` when no secret set.

### Related server-side work (already done, do not redo)

- `xnch/routing/response_sanitize.py` — strips ``/`<think>` from model output
- `xnch/routes/nexi_gateway.py` — applies sanitizer on `/nexi/chat` and `/nexi/chat/stream`
- `cli/client.py` — client-side `strip_thinking()` on chat responses
- Note: `misc/notes/nexi-chat-memory-context-gap.md` documents chat/memory context issues

## Known gaps — implement these (priority order)

### P0 — Session management

**Problem:** CLI persists one `session_id` in `~/.xnch/cli_state.json`. Redis working memory accumulates all REPL turns; Nexi fixates on old hellos and stale context.

**Do:**
1. Add `chat --new-session` — generate fresh `cli-{uuid}` and save to state file
2. Default REPL to new session per launch (or add `--continue` to reuse)
3. Add `session clear` command — document that server has no clear endpoint yet; workaround is new session id (optional: add `DELETE /nexi/session/{id}` on xnch if small scope)

### P1 — Operator ergonomics

1. `consolidate status` — show last consolidation timer run:
   - `systemctl list-timers consolidation.timer`
   - `journalctl -u consolidation.service --since yesterday`
   - Timer: `infra/no-k3s/node-a/systemd/consolidation.timer` (02:00 UTC daily)
2. Print session id on REPL start: `session: cli-abc123`
3. `--json` consistency on all commands (already on most)

### P2 — Chat + memory integration (CLI-only first)

When user message matches recall intent (e.g. `/recall`, `recall memory`, `memory recall`), CLI should:
1. Call `client.memory_recall(query)` 
2. Print results or inject into next chat turn

Do NOT wire full tool loop yet — keep scope CLI-side.

### Out of scope for this task

- Web UI
- MCP host implementation
- Full chat tool loop in nexi_gateway
- Fixing episodic memory pollution (server-side; see note file)

## Code conventions

- Python 3.13+, type annotations on all signatures
- `httpx` sync client in CLI (not async)
- Typer + `Annotated[list[str], typer.Argument(...)]` for multi-word args
- Tests in `tests/test_cli*.py` next to root, not inside `cli/`
- Minimal diff; match existing style in `cli/`
- Do not commit unless asked

## Key files to read first

```
cli/main.py
cli/client.py
cli/util.py
xnch/routes/nexi_gateway.py      # chat API contract
xnch/routes/session.py           # session/init contract
xnch/memory/working_memory.py    # turn storage (no TTL today)
misc/notes/nexi-chat-memory-context-gap.md
```

## Acceptance criteria

- [ ] `python -m cli chat --new-session` starts fresh REPL with new session id shown
- [ ] `python -m cli chat --continue` reuses `~/.xnch/cli_state.json` session (if flag added)
- [ ] `pytest tests/test_cli.py tests/test_cli_util.py` passes
- [ ] New tests for session id generation / `--new-session` behavior
- [ ] No regressions on multi-word `recall`, `run`, `chat`

## Environment (gate7 production)

- Node A: xnch `:8001`, redis, postgres, litellm
- Node B: nexi `:8000`, vllm-ornith `:8082`
- `XNCH_AUTH_SECRET` in `~/.xnch/xnch.env`

Start by reading the existing `cli/` package, then implement P0 session management.
