# Agentic Layer (M1–M5) Implementation Plan — Hermes + Gas Town + LangGraph

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the excluded agent/workflow/goal subsystems with the federated agentic layer: Hermes (node-b, long-horizon autonomy), Gas Town (Mac, burst workstreams), LangGraph (decision + supervisor graphs) — all governed through the MCP bridge choke point.

**Architecture:** Milestones M1–M5 from the spec, sequential, each ending in deploy + verify. One choke point invariant: every governed agent action flows as `xnch_*`/`am_*` tool calls through the gateway (policy → trust tier → audit). New actors get T1 at most; T2 (workstream spawn) is reachable only via the supervisor graph's HITL `interrupt()` running as SYSTEM.

**Tech Stack:** FastAPI, httpx, LangGraph (`langgraph`, `langgraph.types.Command`), pytest (asyncio_mode=auto), systemd (nodes), launchd (Mac), Hermes Agent (Nous Research), Gas Town (gastownhall/gastown).

**Spec:** `docs/superpowers/specs/2026-09-11-agentic-layer-hermes-gastown-langgraph.md`

## Global Constraints

- **Prerequisite gate:** micro-component split Phase 1 + Phase 2 complete and verified in prod (their ops gates confirmed). Do not start M1 otherwise.
- External contracts frozen: pre-existing `xnch_*`/`am_*` tool signatures, muse UI, chat API. New tools are **additive only**.
- `xnch/` and `nexi/` are git submodules — commit inside the submodule first, bump the gitlink in the superrepo at milestone end. `xnch_mcp/`, `scripts/`, `infra/` are superrepo packages.
- AGENTS.md code conventions (modern unions, Pydantic models, `logging.getLogger(__name__)`, relative imports in-package).
- Fail-closed auth everywhere new; no anonymous tool path (the current `/mcp` header-trust is fixed in M2 Task 2.1 before Hermes attaches).
- Run `pytest` from repo root with repo `.venv` active.
- Ops steps (install, systemd/launchd, deploy env) are marked **USER OPS** — executed by the operator on the real hosts, not by the coding agent.

## Discovered facts (verified during planning — trust these)

- `/mcp` HTTP routes (`xnch_mcp/http_router.py:24-28`) derive actor purely from the spoofable `X-Actor-Role` header — **no auth**. Must be fixed before Hermes attaches.
- Trust map (`xnch/security/trust_model.py`): `ACTOR_TRUST_MAP` — add `hermes` there. Tier ceiling (`xnch_mcp/auth.py`): TRUSTED_AGENT → `T1_WRITE`; OWNER/SYSTEM → `T2_EXEC`.
- Exclusion flags already exist and default **false** in config: `goal_dispatch_enabled` (xnch:135), `workflow_executor_enabled` (xnch:198), `langgraph_pipeline` (xnch:186), nexi `goal_driver_enabled` / `workflow_executor_enabled` (nexi/config.py:137-142). M1 verifies the *deployed env* doesn't enable them.
- `_memory_surface` (`xnch_mcp/handlers/memory.py:46-52`) lazily builds `ProactivityEngine` from `app.kv_cache.redis_client` — no flag; M1 adds one.
- `PipelineRuntime` (`xnch/agents/pipeline_runtime.py`) already has checkpointer + interrupt extraction + `parse_resume_decision` resume — M4 promotes it; it is NOT rebuilt from scratch.
- Registry loading (`xnch_mcp/registry.py:_load_handlers`) imports handler modules explicitly — a new `workstream` module must be added to that import list.
- `ToolDef` shape (`xnch_mcp/tool_def.py`): `name, description, tier, input_schema, handler, allowed_actors`.
- Memory-routing default (`xnch/memory/routing_policy.py`): `deprecate_store_note_for=frozenset({"nexi"})` — extend with `hermes`.

---

# MILESTONE 1 — Flag off the excluded subsystems

### Task 1.1: `proactivity_surface_enabled` flag

**Files:**
- Modify: `xnch/config.py` (near `langgraph_pipeline`, line ~186)
- Modify: `xnch_mcp/handlers/memory.py` (`_memory_surface`, line 46)
- Test: `xnch_mcp/tests/test_memory_surface_flag.py` (new)

**Interfaces:**
- Produces: `Settings.proactivity_surface_enabled: bool = True` (`XNCH_PROACTIVITY_SURFACE_ENABLED`); `_memory_surface` returns `[]` when false.

- [ ] **Step 1: Write the failing test**

```python
"""proactivity_surface_enabled gates the muse proactivity surface."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from xnch_mcp.handlers import memory as mem


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    app = SimpleNamespace(kv_cache=SimpleNamespace(redis_client=None))
    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)
    return app


async def test_surface_disabled_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: False)
    result = await mem._memory_surface(SimpleNamespace(), None, {})
    assert result == []


async def test_surface_enabled_uses_engine(app, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Engine:
        async def get_pending(self) -> list[dict]:
            return [{"type": "test"}]

    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)

    created: list = []

    class _EngineFactory:
        def __call__(self, redis) -> _Engine:
            created.append(redis)
            return _Engine()

    import nexi.proactivity.engine as pe

    monkeypatch.setattr(pe, "ProactivityEngine", _EngineFactory())
    result = await mem._memory_surface(app, None, {})
    assert result == [{"type": "test"}]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest xnch_mcp/tests/test_memory_surface_flag.py -v` → FAIL (no `_proactivity_enabled`).

- [ ] **Step 3: Implement**

`xnch/config.py` (after `langgraph_pipeline`):
```python
    proactivity_surface_enabled: bool = True
```

`xnch_mcp/handlers/memory.py` — replace the top of `_memory_surface`:
```python
def _proactivity_enabled() -> bool:
    from xnch.config import settings

    return settings.proactivity_surface_enabled


async def _memory_surface(app: Any, _actor: ActorContext, _args: dict[str, Any]) -> list[dict[str, Any]]:
    if not _proactivity_enabled():
        return []
    if not hasattr(app, "_nexi_proactivity"):
        from nexi.proactivity.engine import ProactivityEngine

        redis = app.kv_cache.redis_client
        app._nexi_proactivity = ProactivityEngine(redis)
    events = await app._nexi_proactivity.get_pending()
    return [e.to_dict() for e in events]
```

- [ ] **Step 4: Run tests** → `pytest xnch_mcp/tests/test_memory_surface_flag.py -v` → 2 PASS; full `pytest xnch_mcp/tests/ -q` green.

- [ ] **Step 5: Commit (submodule `xnch_mcp` is superrepo — plain commit)**

```bash
git add xnch/config.py xnch_mcp/handlers/memory.py xnch_mcp/tests/test_memory_surface_flag.py
git commit -m "feat: proactivity_surface_enabled flag"
```
(`xnch/config.py` is inside the xnch submodule — commit it there first: `git -C xnch add xnch/config.py && git -C xnch commit -m "feat: proactivity_surface_enabled setting"`.)

### Task 1.2: Deploy env verification + regression

- [ ] **Step 1: USER OPS — verify deployed env on node-a (`~/.xnch/xnch.env`) and node-b (`~/.xnch/nexi.env`)** contains none of: `XNCH_GOAL_DISPATCH_ENABLED=true`, `XNCH_WORKFLOW_EXECUTOR_ENABLED=true`, `XNCH_LANGGRAPH_PIPELINE=true`, `NEXI_GOAL_DRIVER_ENABLED=true`, `NEXI_WORKFLOW_EXECUTOR_ENABLED=true` (defaults are already `false`). Restart gateway + nexi. Confirm scheduler log shows only non-excluded jobs (`session_ingest` stays enabled).

- [ ] **Step 2: Regression** — `pytest --tb=short -q` green; e2e chat via `python -m clients.cli mcp test --skip-chat`; muse UI loads.

---

# MILESTONE 2 — Hermes on node-b

### Task 2.1: MCP HTTP router authentication (security fix; resolves spec Open Question 1)

**Files:**
- Modify: `xnch/config.py` (new `mcp_http_token: str = ""`), `xnch_mcp/http_router.py`
- Test: `xnch_mcp/tests/test_http_router_auth.py` (new)

**Interfaces:**
- Produces: when `XNCH_MCP_HTTP_TOKEN` is set, all `/mcp/*` routes require header `X-MCP-Token` (constant-time compare, fail-closed 503 when configured-but-mismatched → use 401 for mismatch, 503 only for misconfig); unset token = current behavior + one warning log (back-compat for local tests). Hermes and cli carry this token.

- [ ] **Step 1: Write the failing test**

```python
"""MCP HTTP router token auth."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from xnch.config import settings as xnch_settings


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(xnch_settings, "mcp_http_token", "sekrit")

    from xnch_mcp.http_router import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_missing_token_401(app) -> None:
    async with _client(app) as client:
        resp = await client.get("/mcp/tools")
    assert resp.status_code == 401


async def test_wrong_token_401(app) -> None:
    async with _client(app) as client:
        resp = await client.get("/mcp/tools", headers={"X-MCP-Token": "nope"})
    assert resp.status_code == 401


async def test_valid_token_passes(app) -> None:
    async with _client(app) as client:
        resp = await client.get(
            "/mcp/tools",
            headers={"X-MCP-Token": "sekrit", "X-Actor-Role": "viewer"},
        )
    assert resp.status_code == 200
    assert resp.json()["actor"] == "viewer"


async def test_unset_token_backcompat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xnch_settings, "mcp_http_token", "")
    from fastapi import FastAPI

    from xnch_mcp.http_router import router

    app = FastAPI()
    app.include_router(router)
    async with _client(app) as client:
        resp = await client.get("/mcp/tools", headers={"X-Actor-Role": "viewer"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run to verify failure** → `pytest xnch_mcp/tests/test_http_router_auth.py -v` → 401 tests FAIL (currently 200).

- [ ] **Step 3: Implement** — in `xnch_mcp/http_router.py`, add after the imports:

```python
import secrets as _secrets

from fastapi import Header as _Header
from typing import Annotated as _Annotated

from xnch.config import settings as _xnch_settings


def _verify_mcp_token(
    token: _Annotated[str | None, _Header(alias="X-MCP-Token")] = None,
) -> None:
    expected = _xnch_settings.mcp_http_token
    if not expected:
        return  # back-compat: unset token keeps legacy behavior (LAN trust)
    if not token or not _secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid MCP token")
```

Then add `_: None = Depends(_verify_mcp_token)` to every route in the router (`/tools`, `/tools/openai`, `/servers`, `/call`, `/call/batch` — `Depends` comes from `fastapi`). Add `mcp_http_token: str = ""` to `xnch/config.py` (submodule commit).

- [ ] **Step 4: Run tests** → 4 PASS; `pytest xnch_mcp/tests/ -q` green (existing http_router tests must be updated to set the token ONLY if they set one — they run with unset token, so they stay green).

- [ ] **Step 5: Commit**

```bash
git -C xnch add xnch/config.py && git -C xnch commit -m "feat: mcp_http_token setting"
git add xnch_mcp/http_router.py xnch_mcp/tests/test_http_router_auth.py
git commit -m "feat(mcp): token auth for HTTP router (prereq for external agents)"
```

### Task 2.2: `hermes` actor at TRUSTED_AGENT

**Files:**
- Modify: `xnch/security/trust_model.py` (`ACTOR_TRUST_MAP`)
- Test: `xnch/tests/test_hermes_actor.py` (new)

- [ ] **Step 1: Failing test**

```python
"""hermes actor: TRUSTED_AGENT tier, T1_WRITE tool ceiling."""

from __future__ import annotations

from xnch.security.trust_model import TrustLevel, get_trust_level
from xnch_mcp.auth import max_tier_for_role
from xnch_mcp.tiers import ToolTier


def test_hermes_trust_level() -> None:
    assert get_trust_level("hermes") is TrustLevel.TRUSTED_AGENT


def test_hermes_max_tier() -> None:
    assert max_tier_for_role("hermes") is ToolTier.T1_WRITE
```

- [ ] **Step 2: Verify failure** → `pytest xnch/tests/test_hermes_actor.py -v` → FAIL (hermes → UNTRUSTED).

- [ ] **Step 3: Implement** — in `ACTOR_TRUST_MAP` add:
```python
    "hermes": TrustLevel.TRUSTED_AGENT,
```

- [ ] **Step 4: Tests pass** → 2 PASS.

- [ ] **Step 5: Commit (submodule)** — `git -C xnch add xnch/security/trust_model.py xnch/tests/test_hermes_actor.py && git -C xnch commit -m "feat: hermes actor at TRUSTED_AGENT"`

### Task 2.3: Skills sync — `scripts/gen_agent_skills.py`

**Files:**
- Create: `scripts/gen_agent_skills.py`
- Test: `tests/test_gen_agent_skills.py` (new)

**Interfaces:**
- Produces: `generate_skills(registry: list[ToolDef], out_dir: Path) -> list[Path]` — one `SKILL.md`-format markdown doc per tool: front matter (`name`, `description`), YAML input schema, tier, example invocation. CLI: `python scripts/gen_agent_skills.py --out ~/.hermes/skills/xnch/` (uses the live registry).

- [ ] **Step 1: Failing test** (uses a fake ToolDef — no registry import)

```python
"""gen_agent_skills: SKILL.md generation from tool defs."""

from __future__ import annotations

from pathlib import Path

from xnch_mcp.tool_def import ToolDef
from xnch_mcp.tiers import ToolTier

from scripts.gen_agent_skills import generate_skills


def _tool(name: str = "xnch_memory_recall") -> ToolDef:
    async def handler(app, actor, args):  # pragma: no cover
        return {}

    return ToolDef(
        name=name,
        description="Recall episodes.",
        tier=ToolTier.T0_READ,
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        handler=handler,
    )


def test_generates_skill_md(tmp_path: Path) -> None:
    paths = generate_skills([_tool()], tmp_path)
    assert len(paths) == 1
    content = paths[0].read_text()
    assert "xnch_memory_recall" in content
    assert "description" in content
    assert "T0_READ" in content


def test_no_tools_no_files(tmp_path: Path) -> None:
    assert generate_skills([], tmp_path) == []
```

(Note: `scripts/` has no `__init__.py` — import via `from gen_agent_skills import ...` with `sys.path` including `scripts/`, or add a small `scripts/__init__.py`. Prefer the latter if the import above fails.)

- [ ] **Step 2: Verify failure** → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
"""Generate agentskills.io-format SKILL.md docs for xnch MCP tools.

Usage: python scripts/gen_agent_skills.py --out <dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from xnch_mcp.registry import get_registry


def _skill_md(tool) -> str:
    front = {
        "name": tool.name,
        "description": tool.description,
        "tier": tool.tier.name,
    }
    body = [
        "---",
        yaml.safe_dump(front, sort_keys=False).strip(),
        "---",
        "",
        f"# {tool.name}",
        "",
        f"{tool.description}",
        "",
        "## Input schema",
        "",
        "```yaml",
        yaml.safe_dump(tool.input_schema, sort_keys=False).strip(),
        "```",
        "",
    ]
    return "\n".join(body)


def generate_skills(registry: list, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for tool in registry:
        path = out_dir / f"{tool.name}.skill.md"
        path.write_text(_skill_md(tool))
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paths = generate_skills(get_registry(), args.out)
    print(f"wrote {len(paths)} skills to {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests pass** → 2 PASS.

- [ ] **Step 5: Commit** — `git add scripts/gen_agent_skills.py tests/test_gen_agent_skills.py && git commit -m "feat: SKILL.md generator for agent skills sync"`

### Task 2.4: Memory routing — add `hermes` to deprecation default

**Files:**
- Modify: `xnch/memory/routing_policy.py` (default fallback, ~line 33 and ~line 41)
- Test: extend `xnch/tests/test_memory_routing_policy.py`

- [ ] **Step 1: Failing test** — append:

```python
def test_default_deprecates_hermes(tmp_path):
    from xnch.memory.routing_policy import load_memory_routing_policy

    policy = load_memory_routing_policy(tmp_path / "does-not-exist.yaml")
    assert "hermes" in policy.deprecate_store_note_for
    assert "nexi" in policy.deprecate_store_note_for
```

- [ ] **Step 2: Verify failure** → FAIL (default is `{"nexi"}`).

- [ ] **Step 3: Implement** — change both default constructions in `routing_policy.py` to `frozenset({"nexi", "hermes"})` and `deprecated = data.get("deprecate_store_note_for") or ["nexi", "hermes"]`. Update the example YAML `infra/no-k3s/shared/memory-routing.example.yaml` accordingly (and the deployed `~/.xnch/memory-routing.yaml` at M2 ops).

- [ ] **Step 4: Tests pass** (existing test asserting `{"nexi"}` on explicit YAML lists still passes — it sets its own list).

- [ ] **Step 5: Commit (submodule)** — `git -C xnch add xnch/memory/routing_policy.py xnch/tests/test_memory_routing_policy.py && git -C xnch commit -m "feat: hermes added to store_note deprecation default"`

### Task 2.5: Hermes deployment + soak (ops)

**Files:**
- Create: `infra/no-k3s/node-b/systemd/hermes.service`, `docs/runbooks/hermes-deploy.md`

- [ ] **Step 1: Unit file**

```ini
[Unit]
Description=Hermes Agent — long-horizon autonomy (node-b)
After=network.target

[Service]
Type=simple
User=x-nch
WorkingDirectory=/home/x-nch
EnvironmentFile=/home/x-nch/.xnch/hermes.env
ExecStart=/usr/bin/env hermes agent --daemon
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```
(The exact `ExecStart` comes from the Hermes install docs at hermes-agent.org — adjust to match the installed version's daemon invocation; the unit's job is lifecycle + env, nothing more.)

- [ ] **Step 2: `hermes.env` template** (documented in the runbook, values filled by operator):
```
# Model: local Ornith via LiteLLM (OpenAI-compatible), OpenRouter fallback
HERMES_LLM_BASE_URL=http://127.0.0.1:4000/v1
HERMES_LLM_MODEL=ornith-1.0-35b
# xnch MCP bridge (HTTP transport)
XNCH_MCP_URL=http://192.168.50.1:8001/mcp
XNCH_MCP_TOKEN=<same as XNCH_MCP_HTTP_TOKEN on gateway>
XNCH_ACTOR_ROLE=hermes
```
(Wire Hermes's MCP client to those values per its config format; `X-Actor-Role: hermes` + `X-MCP-Token` on every call.)

- [ ] **Step 3: Runbook** `docs/runbooks/hermes-deploy.md` — install steps (upstream docs), env setup, skills sync (`python scripts/gen_agent_skills.py --out <hermes skills dir>`), systemd install, soak checklist:
  1. Hermes lists tools: `GET /mcp/tools` with hermes headers → only ≤T1 tools visible.
  2. Recall works: automation runs `xnch_memory_recall`.
  3. Governed exec works: automation runs a T1 tool; a T2 attempt is denied (403) — verify in audit.
  4. Durable write routed: `am_memory_save` succeeds; `xnch_memory_store_note` from hermes → deprecation error.
  5. One full automation appears end-to-end in the DecisionLedger.

- [ ] **Step 4: USER OPS — run the soak.** Do not proceed to M3 until checklist item 5 passes.

- [ ] **Step 5: Commit + bump gitlinks** (xnch submodule from Tasks 2.2/2.4; superrepo artifacts):
```bash
git add infra/no-k3s/node-b/systemd/hermes.service docs/runbooks/hermes-deploy.md xnch
git commit -m "feat(hermes): node-b unit, env template, deploy runbook + submodule bump"
```

---

# MILESTONE 3 — Gas Town on the Mac

### Task 3.1: `GastownClient` + settings

**Files:**
- Modify: `xnch/config.py` (new settings)
- Create: `xnch_mcp/gastown.py`
- Test: `xnch_mcp/tests/test_gastown_client.py` (new)

**Interfaces:**
- Produces: `Settings.gastown_url: str = ""`, `Settings.gastown_token: str = ""` (`XNCH_GASTOWN_URL`, `XNCH_GASTOWN_TOKEN`); `GastownClient(base_url, token, timeout=15.0, transport=None)` with:
  - `async def spawn(title: str, goal: str, workspace_hint: str | None = None, agent_hint: str | None = None) -> dict` → POST `{GASTOWN_SPAWN_PATH}` (default `/api/workstreams`)
  - `async def status(workstream_id: str | None = None) -> dict` → GET `/api/workstreams` or `/api/workstreams/{id}`
  - raises `GastownError` on non-2xx/transport failure.
- Path constants live in the class (`SPAWN_PATH = "/api/workstreams"`) — **verify against the installed Gas Town version at M3 ops and adjust before deploy** (spec Open Question 2 resolution: direct POST gateway→Mac over tailscale; documented fallback is status-polling only).

- [ ] **Step 1: Failing test**

```python
"""GastownClient: spawn/status HTTP shapes."""

from __future__ import annotations

import httpx
import pytest

from xnch_mcp.gastown import GastownClient, GastownError


def _ok(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


async def test_spawn_posts_workstream() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(200, json={"id": "ws-1", "state": "queued"})

    client = GastownClient(
        "http://mac:7474", token="t", transport=httpx.MockTransport(handler)
    )
    result = await client.spawn("fix login bug", "Fix the login timeout", workspace_hint="xnch")
    assert result["id"] == "ws-1"
    assert seen["path"] == "/api/workstreams"
    import json

    body = json.loads(seen["body"])
    assert body["title"] == "fix login bug"
    assert body["goal"] == "Fix the login timeout"


async def test_status_gets_workstreams() -> None:
    client = GastownClient(
        "http://mac:7474", token="t",
        transport=_ok({"workstreams": [{"id": "ws-1", "state": "running"}]}),
    )
    result = await client.status()
    assert result["workstreams"][0]["state"] == "running"


async def test_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = GastownClient(
        "http://mac:7474", token="t", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(GastownError):
        await client.status()
```

- [ ] **Step 2: Verify failure** → module missing.

- [ ] **Step 3: Implement** `xnch_mcp/gastown.py` (mirrors `RemoteStoreRef` style: httpx AsyncClient per call, token header `Authorization: Bearer <token>`, `GastownError(Exception)`, `raise_for_status` mapped to `GastownError`). Add the two settings to `xnch/config.py` (submodule commit).

- [ ] **Step 4: Tests pass** → 3 PASS. **Step 5: Commit** (submodule for config; superrepo for gastown module):
```bash
git -C xnch add xnch/config.py && git -C xnch commit -m "feat: gastown_url/gastown_token settings"
git add xnch_mcp/gastown.py xnch_mcp/tests/test_gastown_client.py
git commit -m "feat: GastownClient for Mac workstream manager"
```

### Task 3.2: `xnch_workstream_spawn` + `xnch_workstream_status` tools

**Files:**
- Create: `xnch_mcp/handlers/workstream.py`
- Modify: `xnch_mcp/registry.py` (`_load_handlers` import list), `xnch_mcp/handlers/__init__.py` (if it re-exports)
- Test: `xnch_mcp/tests/test_workstream_handlers.py` (new)

**Interfaces:**
- Produces:
  - `xnch_workstream_spawn` — tier `T2_EXEC`, `allowed_actors=None` (trust gate: OWNER/SYSTEM only — this IS the HITL boundary per the architecture; `hermes` at T1 cannot call it directly, only via the M4 supervisor graph interrupt). Handler: build `GastownClient` from settings, `spawn(...)`, emit audit event, return result.
  - `xnch_workstream_status` — tier `T0_READ`. Handler: `status(workstream_id)`; **outcome ingestion**: when a workstream is terminal (`completed`/`failed`) and `pg_episodic.has_identical_recent(f"workstream {id} {state}", hours=24)` is False, store an episode `type_="workstream"` via `app.pg_episodic.store_episode` — idempotent outcome records.

- [ ] **Step 1: Failing test**

```python
"""workstream tools: spawn (T2) + status (T0) with outcome ingestion."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from xnch_mcp.gastown import GastownClient
from xnch_mcp.handlers.workstream import TOOLS
from xnch_mcp.tiers import ToolTier
from xnch_mcp.tool_def import ToolDef


def _defs() -> dict[str, ToolDef]:
    return {t.name: t for t in TOOLS}


def test_tiers() -> None:
    defs = _defs()
    assert defs["xnch_workstream_spawn"].tier is ToolTier.T2_EXEC
    assert defs["xnch_workstream_status"].tier is ToolTier.T0_READ


async def test_spawn_calls_gastown(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list = []

    class _Client:
        async def spawn(self, **kwargs):
            spawned.append(kwargs)
            return {"id": "ws-9", "state": "queued"}

    monkeypatch.setattr(
        "xnch_mcp.handlers.workstream.GastownClient",
        lambda: _Client(),
    )
    app = SimpleNamespace(pg_episodic=SimpleNamespace())
    defs = _defs()
    result = await defs["xnch_workstream_spawn"].handler(
        app, None, {"title": "t", "goal": "g"}
    )
    assert result["id"] == "ws-9"
    assert spawned[0]["title"] == "t"


async def test_status_stores_terminal_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: list = []

    class _Pg:
        async def has_identical_recent(self, raw_text: str, hours: int = 24) -> bool:
            return False

        async def store_episode(self, type_, raw_text=None, importance=1.0) -> str:
            stored.append((type_, raw_text))
            return "m-1"

    class _Client:
        async def status(self, workstream_id=None):
            return {"workstreams": [{"id": "ws-1", "state": "completed", "title": "t"}]}

    monkeypatch.setattr(
        "xnch_mcp.handlers.workstream.GastownClient",
        lambda: _Client(),
    )
    app = SimpleNamespace(pg_episodic=_Pg())
    defs = _defs()
    result = await defs["xnch_workstream_status"].handler(app, None, {})
    assert result["workstreams"][0]["state"] == "completed"
    assert stored and stored[0][0] == "workstream"
```

- [ ] **Step 2: Verify failure** → module missing.

- [ ] **Step 3: Implement** `xnch_mcp/handlers/workstream.py` following the scraper handler pattern (`TOOLS: list[ToolDef]`, private async handlers, `app` from gateway state). Key handler code:

```python
"""Gas Town workstream tools — spawn (T2) and status (T0)."""

from __future__ import annotations

import logging
from typing import Any

from xnch_mcp.context import ActorContext
from xnch_mcp.gastown import GastownClient
from xnch_mcp.tiers import ToolTier
from xnch_mcp.tool_def import ToolDef

logger = logging.getLogger(__name__)

_TERMINAL = {"completed", "failed"}


def _client() -> GastownClient:
    from xnch.config import settings

    if not settings.gastown_url:
        raise ValueError("gastown not configured (XNCH_GASTOWN_URL)")
    return GastownClient(settings.gastown_url, token=settings.gastown_token)


async def _spawn(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    title = str(args.get("title", "")).strip()
    goal = str(args.get("goal", "")).strip()
    if not title or not goal:
        raise ValueError("title and goal are required")
    client = _client()
    result = await client.spawn(
        title,
        goal,
        workspace_hint=args.get("workspace_hint"),
        agent_hint=args.get("agent_hint"),
    )
    if getattr(app, "event_log", None) is not None:
        app.event_log.emit("workstream", "gateway", "WORKSTREAM_SPAWNED", data=result)
    return result


async def _status(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    result = await client.status(args.get("workstream_id"))
    pg = getattr(app, "pg_episodic", None)
    if pg is not None:
        for ws in result.get("workstreams", []):
            if ws.get("state") not in _TERMINAL:
                continue
            marker = f"workstream {ws.get('id')} {ws.get('state')}"
            if not await pg.has_identical_recent(marker, hours=24):
                await pg.store_episode(
                    type_="workstream",
                    raw_text=f"{marker}: {ws.get('title', '')}",
                    importance=2.0,
                )
    return result


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_workstream_spawn",
        description="Spawn a Gas Town coding-agent workstream on the Mac (git-backed).",
        tier=ToolTier.T2_EXEC,
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "goal": {"type": "string"},
                "workspace_hint": {"type": "string"},
                "agent_hint": {"type": "string"},
            },
            "required": ["title", "goal"],
        },
        handler=_spawn,
    ),
    ToolDef(
        name="xnch_workstream_status",
        description="List Gas Town workstreams (all, or one by id). Stores terminal outcomes as memory episodes.",
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {"workstream_id": {"type": "string"}},
        },
        handler=_status,
    ),
]
```

Register: in `xnch_mcp/registry.py::_load_handlers` add `workstream` to the import and to the module tuple.

- [ ] **Step 4: Tests pass** → 3 PASS; `pytest xnch_mcp/tests/test_registry.py -q` — the registry grows by exactly 2 tools (update any exact-count assertions to `>= previous + 2`; signature-stability golden test must show additive-only diff).

- [ ] **Step 5: Commit**
```bash
git add xnch_mcp/handlers/workstream.py xnch_mcp/tests/test_workstream_handlers.py xnch_mcp/registry.py
git commit -m "feat(mcp): xnch_workstream_spawn (T2) + xnch_workstream_status (T0) tools"
```

### Task 3.3: Gas Town install + agent-runner retirement (ops)

**Files:**
- Create: `clients/gastown/com.xnch.gastown.plist` (template), `docs/runbooks/gastown-deploy.md`

- [ ] **Step 1: USER OPS — install Gas Town on the Mac** per gastownhall/gastown docs. Init a workspace root (e.g. `~/xnch-workstreams/`). Verify the HTTP API responds; **record the real spawn/status paths and fix `GastownClient` path constants if they differ** (add a regression test with the confirmed paths).

- [ ] **Step 2: launchd plist template** (mirror the retired agent-runner plist: REPO placeholder, KeepAlive):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.xnch.gastown</string>
  <key>WorkingDirectory</key><string>/Users/USER/xnch-workstreams</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/gastown</string>
    <string>serve</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/Users/USER/xnch-agents/gastown.log</string>
  <key>StandardErrorPath</key><string>/Users/USER/xnch-agents/gastown.err</string>
</dict>
</plist>
```
(Adjust `ProgramArguments` to the installed binary's serve command.)

- [ ] **Step 3: Runbook** — install, plist load, tailscale reachability check from node-a (`curl http://<mac>:<port>/api/workstreams`), token config, end-to-end: `python -m clients.cli` (or curl) → `xnch_workstream_spawn` as `operator` → workstream appears on Mac → `xnch_workstream_status` shows it → terminal outcome findable via `xnch_memory_recall`.

- [ ] **Step 4: USER OPS — retire agent-runner**: `launchctl unload ~/Library/LaunchAgents/com.xnch.agent-runner.plist`; leave code in tree until M5.

- [ ] **Step 5: Commit** — `git add clients/gastown/ docs/runbooks/gastown-deploy.md && git commit -m "feat(gastown): launchd template + deploy runbook; agent-runner retired"`

---

# MILESTONE 4 — LangGraph consolidation

### Task 4.1: Relax the Phase 2 remote-memory guard

**Files:**
- Modify: `xnch/main.py` (LangGraph guard from Phase 2 Task 8 Step 2)
- Test: `xnch/tests/test_langgraph_remote_mode.py` (new)

- [ ] **Step 1: Failing test**

```python
"""LangGraph runtime may run with remote-memory backends (Phase 2 refs)."""

from __future__ import annotations

from types import SimpleNamespace

import xnch.main as main_mod


def test_no_embedded_only_guard() -> None:
    src = main_mod.__file__
    import inspect

    body = inspect.getsource(main_mod)
    assert "requires XNCH_MEMORY_EMBEDDED=1" not in body, (
        "LangGraph must no longer be gated on embedded memory"
    )
```
(A source assertion is deliberate: the guard was a string-logged condition; after removal, `PipelineRuntime` receives `s.memory.*` backends which are Phase 2 refs in remote mode — `RemoteGraphStore` sync proxy + async refs were built for this.)

Additionally run the existing LangGraph tests in remote mode (they use injected checkpoints/stores — no change needed): `pytest xnch/tests/test_pipeline_hitl.py xnch/tests/test_hitl.py -q` green.

- [ ] **Step 2: Implement** — in `xnch/main.py`, delete the `elif settings.langgraph_pipeline:` warning branch and the `and settings.memory_embedded` condition so the guard is simply `if settings.langgraph_pipeline:` (runtime gets `s.memory` backends: `working_memory`, `pg_episodic`, `graph_store`, `relationship_store`, `sensory_buffer` — update the `stores=` dict to use `s.memory.*` attributes).

- [ ] **Step 3: Tests pass** → new test PASS; full `pytest xnch/tests -q` green.

- [ ] **Step 4: Commit (submodule)** — `git -C xnch add xnch/main.py xnch/tests/test_langgraph_remote_mode.py && git -C xnch commit -m "feat: langgraph runtime runs with remote memory backends"`

### Task 4.2: `workstream_supervisor` graph

**Files:**
- Create: `xnch/agents/supervisor_graph.py`
- Test: `xnch/tests/test_supervisor_graph.py` (new)

**Interfaces:**
- Produces: `build_supervisor(checkpointer: Any | None = None) -> CompiledGraph` — a LangGraph with one decision node + `interrupt()` gate:
  - Input state: `{"goal_text": str, "actor": str}`
  - Node `decide`: heuristic (v1, no LLM): if goal matches coding-intent regex (`\b(implement|fix|refactor|write|build)\b` …) → propose `spawn_workstream`; else → `{"action": "none"}`.
  - Node `gate`: if proposal is spawn → `interrupt({"type": "workstream_spawn", "goal_text": ...})`; on `Command(resume=True)` → invoke the `xnch_workstream_spawn` tool via the registry (SYSTEM actor); on resume False → `{"action": "rejected"}`.
  - Terminal state: `{"action": "spawned"|"rejected"|"none", "workstream_id": ...}`.

- [ ] **Step 1: Write the failing tests**

```python
"""supervisor graph: coding intent → interrupt → spawn on approve."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from xnch.agents.supervisor_graph import build_supervisor


@pytest.fixture
def spawned():
    return SimpleNamespace(calls=[])


@pytest.fixture
def graph(monkeypatch: pytest.MonkeyPatch, spawned):
    async def fake_spawn(app, actor, args):
        spawned.calls.append(args)
        return {"id": "ws-42", "state": "queued"}

    import xnch.agents.supervisor_graph as sg

    monkeypatch.setattr(sg, "_spawn_tool", fake_spawn)
    return build_supervisor(checkpointer=MemorySaver())


async def test_non_coding_goal_no_spawn(graph, spawned) -> None:
    result = await graph.ainvoke(
        {"goal_text": "what is the weather", "actor": "operator"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert result["action"] == "none"
    assert spawned.calls == []


async def test_coding_goal_interrupts_then_spawns(graph, spawned) -> None:
    cfg = {"configurable": {"thread_id": "t2"}}
    result = await graph.ainvoke(
        {"goal_text": "fix the login timeout bug", "actor": "operator"}, config=cfg
    )
    assert result["action"] == "awaiting_approval"
    result2 = await graph.ainvoke(Command(resume=True), config=cfg)
    assert result2["action"] == "spawned"
    assert result2["workstream_id"] == "ws-42"
    assert spawned.calls and spawned.calls[0]["goal"].startswith("fix the login")


async def test_rejection_skips_spawn(graph, spawned) -> None:
    cfg = {"configurable": {"thread_id": "t3"}}
    await graph.ainvoke(
        {"goal_text": "build the dashboard widget", "actor": "operator"}, config=cfg
    )
    result = await graph.ainvoke(Command(resume=False), config=cfg)
    assert result["action"] == "rejected"
    assert spawned.calls == []
```

- [ ] **Step 2: Verify failure** → module missing.

- [ ] **Step 3: Implement** `xnch/agents/supervisor_graph.py` — LangGraph `StateGraph` with `decide` and `gate` nodes as specified; module-level `async def _spawn_tool(app, actor, args)` that calls the registered tool (patch point for tests). Follow `pipeline_graph.py`'s graph-building style (`add_node`, `add_edge`, `add_conditional_edges`, `compile(checkpointer=...)`).

- [ ] **Step 4: Tests pass** → 3 PASS.

- [ ] **Step 5: Commit (submodule)** — `git -C xnch add xnch/agents/supervisor_graph.py xnch/tests/test_supervisor_graph.py && git -C xnch commit -m "feat: workstream supervisor graph with HITL interrupt"`

### Task 4.3: Proactivity surface re-target

**Files:**
- Modify: `xnch_mcp/handlers/memory.py` (`_memory_surface`)
- Test: extend `xnch_mcp/tests/test_memory_surface_flag.py`

- [ ] **Step 1: Failing test** — append:

```python
async def test_surface_reads_recent_agent_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Pg:
        async def fetch_by_type(self, type_, limit=20):
            assert type_ == "workstream"
            return [{"raw_text": "workstream ws-1 completed", "type": "workstream"}]

    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)
    app = SimpleNamespace(pg_episodic=_Pg(), kv_cache=SimpleNamespace(redis_client=None))
    result = await mem._memory_surface(app, None, {})
    assert result and result[0]["raw_text"] == "workstream ws-1 completed"
```

- [ ] **Step 2: Verify failure** (current impl returns ProactivityEngine events).

- [ ] **Step 3: Implement** — replace the engine path in `_memory_surface`:
```python
async def _memory_surface(app: Any, _actor: ActorContext, _args: dict[str, Any]) -> list[dict[str, Any]]:
    if not _proactivity_enabled():
        return []
    pg = getattr(app, "pg_episodic", None)
    if pg is None:
        return []
    events: list[dict[str, Any]] = []
    for type_ in ("workstream", "automation"):
        rows = await pg.fetch_by_type(type_, limit=20)
        events.extend(rows)
    return events
```
(Degrades gracefully pre-M5 — ProactivityEngine is no longer imported; `nexi.proactivity` becomes dead code, deleted in M5.)

- [ ] **Step 4: Tests pass** (the M1 engine test is superseded — update it to the new contract).

- [ ] **Step 5: Commit** — `git add xnch_mcp/handlers/memory.py xnch_mcp/tests/test_memory_surface_flag.py && git commit -m "feat: proactivity surface reads agent activity episodes"`

### Task 4.4: Enable LangGraph by default (ops)

- [ ] **Step 1: USER OPS** — set `XNCH_LANGGRAPH_PIPELINE=true` in node-a env; restart gateway; run `pytest xnch/tests/test_pipeline_hitl.py` once against the live gateway is NOT needed (unit tests cover); instead: e2e chat pass + one HITL approval round-trip in muse.
- [ ] **Step 2: Commit gitlink bump** for the xnch submodule (Tasks 4.1–4.3).

---

# MILESTONE 5 — Delete the excluded code

### Task 5.1: Delete excluded subsystems

**Files (delete):**
- `nexi/nexi/goal/`, `nexi/nexi/proactivity/`, `nexi/nexi/workflow/` (submodule — paths relative: `nexi/goal/` etc.)
- `xnch/xnch/jobs/goal_dispatch.py`, `xnch/xnch/jobs/workflow_schedule.py`
- `xnch/xnch/memory/workflow_store.py`, `xnch/xnch/memory/agent_run_store.py`
- `clients/agent-runner/` (superrepo)

**Files (modify for dangling references):**
- `nexi/nexi/main.py` (goal/workflow task blocks, lines ~122–147)
- `xnch/xnch/main.py` (imports of deleted jobs/stores; `workflow_store`/`agent_run_store` wiring; `workflow_schedule` sync block; scheduler jobs referencing them; `routes/__init__.py` workflows_router/approvals wiring if it imports the deleted stores — check `rg -n "workflow_store|agent_run_store|goal_dispatch|workflow_schedule|proactivity" xnch/ nexi/ --type py` first and fix every hit)
- Route deletions: `xnch/routes/workflows.py`, `agents.py`, `approvals.py` IF they exist solely for the excluded machinery — **verify by reading each router first**; keep approvals surface if it serves the new HITL interrupts (it does — HITL resume endpoints). Delete only what is exclusively old-workflow.

- [ ] **Step 1: Inventory dangling references**

Run: `rg -n "workflow_store|agent_run_store|goal_dispatch|workflow_schedule|proactivity|nexi\.goal|nexi\.workflow" xnch nexi xnch_mcp tests --type py | grep -v test_ | grep -v "agents/" `
Expected: the modify-list above and nothing else. Fix any surprise before deleting.

- [ ] **Step 2: Delete + fix imports**, submodule by submodule (`git -C xnch rm ...`, `git -C nexi rm ...`), superrepo last (`git rm -r clients/agent-runner`).

- [ ] **Step 3: Full suite green** — `pytest --tb=short -q`. Delete tests that covered only excluded code; do not weaken surviving tests.

- [ ] **Step 4: Commit** (per submodule, then gitlink bumps):
```bash
git -C xnch commit -m "chore: remove excluded workflow/goal-dispatch stores and jobs"
git -C nexi commit -m "chore: remove goal/proactivity/workflow subsystems (replaced by Hermes/Gas Town)"
git add xnch nexi && git commit -m "chore: bump submodules — excluded agent machinery removed"
git rm -r clients/agent-runner && git commit -m "chore: remove agent-runner (replaced by Gas Town)"
```

### Task 5.2: Flags + docs cleanup

- [ ] **Step 1:** Remove the now-dead flags from both configs (`goal_dispatch_*`, `workflow_executor_enabled` on both, nexi `goal_driver_*`, `workflow_poll_*`, `goal_default_*`) **only if no remaining code references them** (verify by grep). Keep `proactivity_surface_enabled` (it gates the new surface) and `langgraph_pipeline` (now true in deploy).
- [ ] **Step 2:** Update `AGENTS.md` Single-Home Registry — new homes: scheduling/autonomy → Hermes (node-b), workstreams → Gas Town (Mac) via `xnch_workstream_*` tools, decision/supervisor graphs → `xnch/agents/` LangGraph. Update `docs/architecture-suite.md`, README mental model.
- [ ] **Step 3: Commit** — `git add AGENTS.md docs/ && git commit -m "docs: single-home registry + architecture for the agentic layer"`

### Task 5.3: Final verification + spec status

- [ ] **Step 1: E2E** — all spec success criteria demonstrated: soak automation chain in DecisionLedger; workstream spawn→status→recall round-trip; HITL interrupt/resume in muse; full `pytest` green; `python -m clients.cli mcp test --skip-chat`.
- [ ] **Step 2:** Contract check — MCP registry contains all pre-existing tools with identical schemas + exactly 2 new (`xnch_workstream_*`).
- [ ] **Step 3:** Update both specs' status (agentic-layer spec → implemented; mark Open Questions 1–2 resolved with the chosen answers). Commit.
- [ ] **Step 4:** Final gitlink bumps + push all repos.

---

## Risks specific to execution (beyond the spec's table)

| Risk | Mitigation in plan |
|---|---|
| Gas Town real API paths differ from assumed `/api/workstreams` | Task 3.3 Step 1 verifies + regression-tests the confirmed paths before any deploy |
| Hermes daemon invocation differs by version | Task 2.5 unit is lifecycle-only; ExecStart confirmed against installed version in runbook |
| M5 deletes something the new layer needs (approvals/HITL) | Task 5.1 Step 1 requires reading routers before deleting; approvals surface explicitly kept |
| Registry count assertions break | Task 3.2 Step 4 updates counts additively; golden test asserts signature stability |
| Supervisor graph test uses langgraph internals | MemorySaver + Command(resume=...) are stable public APIs; tests pin thread_ids |
