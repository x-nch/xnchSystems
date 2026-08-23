# Tests & Verification

Sources: root `pyproject.toml` (`pytest.ini_options`, asyncio_mode=auto),
`tests/`, `*/tests/`.

## Layout

| Suite | Location | Notes |
|---|---|---|
| e2e | `tests/` | cross-service: chat e2e, gateway, goals loop, scraper, voice API/IO, cli |
| nexi unit | `nexi/tests/` | pipeline, evaluator, adapters |
| xnch unit | `xnch/tests/` | routes, stores, policy, security |
| xnch_mcp | `xnch_mcp/tests/` | registry, tiers, exec/fs handlers, http router |
| xnch-train | `xnch-train/tests/` | extractor, scrubber, manifest, gate boundaries, runner |

## Commands

```bash
git submodule update --init --recursive   # first time
uv sync --all-groups                      # project + dev + voice groups (Python 3.13+)
pytest                                    # everything
pytest tests                              # e2e only
pytest nexi/tests                         # nexi only
pytest xnch/tests                         # xnch only
pytest -k "workflow"                      # by keyword
pytest -x --no-header                     # fail fast
pytest --cov=nexi --cov=xnch              # coverage
```

All tests run async automatically (`asyncio_mode = "auto"`); xnch store tests
use `fakeredis`. No dedicated lint/typecheck commands exist at the root
(`npm run lint` exists inside `web/` for the muse app).

### Fresh-env reality (verified 2026-08-23)

On a brand-new clone, `uv sync` + `pytest --collect-only` yields
**460 collected / 44 collection errors** — the root project does not pin every
submodule runtime dep (`redis`, `apscheduler`, voice extras). Operator hosts
carry the full env where plain `pytest` works. When contributing from a fresh
clone, either add the missing deps to your env or run only the suites whose
deps you have; the three pre-existing failures below still apply regardless.

## Known pre-existing failures (NOT regressions)

These fail before any current work; do not treat as breakage when verifying:

1. `tests/test_voice_io.py`
2. `xnch_mcp` exec/fs handler tests
3. `tests/test_nexi_chat_e2e.py`

When adding features, compare against this baseline rather than demanding a
fully green run. New failures beyond these three are regressions.

## Web (muse)

```bash
cd web && npm install && npm run dev     # dev server
npm run build                            # production build
npm run lint                             # eslint
```

Unit tests via vitest config present (`vitest.config.ts`); run with
`npx vitest run` [UNVERIFIED].
