# Phase 1 — Capability Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `exec_agent/` + `fs_read_agent/` into one capability sidecar, retarget `xnch_mcp` behind it with a zero-risk env flip, group clients, and document single-homes — no external contract changes.

**Architecture:** A new `capability_agent/` package (superrepo) serves both governed-exec and read-only-fs on one port (:8090) with one shared token, accepting legacy per-capability tokens during migration. `xnch_mcp`'s dispatch services gain a `capability_*`-first, legacy-fallback settings chain so the cutover is a single env change with instant rollback. Memory-routing enforcement (spec §5.4) was verified already implemented and tested during planning (`xnch_mcp/handlers/memory.py:56-64`, `xnch_mcp/tests/test_memory_routing.py:21-45`) — no code needed, only documentation.

**Tech Stack:** FastAPI, uvicorn, httpx, pydantic-settings, pytest (asyncio_mode=auto), systemd.

**Spec:** `docs/superpowers/specs/2026-09-11-micro-component-split.md` — implements Phase 1 (T0.1–T0.2, T1.1–T1.8). Tasks below map: Task 1→T0.1, Tasks 2–5→T1.1+T1.2, Task 6→T1.3 (infra prep; node-b cutover is user-run ops), Task 7→T1.4, Task 8→T1.5+T1.6, Task 9→T1.7, Task 10→T1.8, Task 11→verification.

## Global Constraints

- External contracts frozen: `xnch_*`/`am_*` MCP tool signatures, web UI, chat API, agent-runner dispatch — byte-identical after Phase 1.
- `xnch/` is a git submodule: changes there are committed inside the submodule first, then the superrepo gitlink is bumped in a follow-up commit (`chore(xnch): bump to <sha> (<what>)`).
- No cross-submodule absolute imports (`from xnch.X import Y` from superrepo packages IS allowed — superrepo packages already do this: `exec_agent/server.py:14-16`; the forbidden pattern is sibling-submodule imports, e.g. nexi importing xnch).
- All auth is fail-closed: unconfigured token = HTTP 503, never open access.
- Python 3.13 repo venv; run `pytest` from repo root with the repo `.venv` active (asyncio_mode=auto — no `@pytest.mark.asyncio` needed, but it's harmless where existing tests use it).
- Commit style: conventional commits, one logical change per commit, matching `git log --oneline` (e.g. `feat:`, `chore:`, `docs:`).
- Ports: capability sidecar `:8090` on node-b (replaces `:8003` fs + `:8004` exec).

## File Structure

```
capability_agent/               # NEW — merged sidecar (superrepo package)
  __init__.py                   # exports app
  __main__.py                   # uvicorn entrypoint (XNCH_CAPABILITY_BIND/PORT)
  app.py                        # FastAPI app mounting both routers + root /health
  exec_router.py                # /exec/run, /exec/health (ported from exec_agent/server.py)
  fs_router.py                  # /fs/list|read|stat|exists|glob|health (ported from fs_read_agent/server.py)
  tests/
    __init__.py
    test_exec_router.py         # token + error-mapping tests (fake backend)
    test_fs_router.py           # ported from fs_read_agent/tests/test_server.py + token tests

xnch/config.py                  # MODIFY — add capability_token, capability_node_b_url (submodule)
xnch_mcp/exec/remote_client.py  # MODIFY — /exec/* paths + injectable transport
xnch_mcp/fs/remote_client.py    # MODIFY — /fs/* paths + injectable transport
xnch_mcp/exec/service.py        # MODIFY — capability-first URL/token fallback
xnch_mcp/fs/service.py          # MODIFY — capability-first URL/token fallback
xnch_mcp/tests/test_remote_clients.py   # NEW — path + fallback tests (MockTransport)

infra/no-k3s/node-b/systemd/xnch-capability.service   # NEW unit
infra/no-k3s/shared/exec-policy.yaml                  # MODIFY — curl allowlist :8003/:8004 → :8090
docs/reference/env-vars.md, mcp-config.md            # MODIFY — new env vars
docs/runbooks/capability-sidecar-deploy.md            # NEW — cutover + rollback runbook
docs/architecture/execution-boundary.md               # NEW — boundary audit (Task 9)
clients/cli/ + clients/agent-runner/                   # MOVED (Task 10)
AGENTS.md                                             # MODIFY — Single-Home Registry (Task 8)
```

---

### Task 1: Baseline verification

**Files:** none (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest --tb=short -q`
Expected: all green (or record pre-existing failures in `misc/phase1-baseline.txt` so they aren't blamed on this work).

- [ ] **Step 2: Record service inventory**

Run: `git submodule status && ls infra/no-k3s/node-b/systemd/`
Expected: `exec-agent.service`, `fs-read-agent.service` present (pre-merge state).

---

### Task 2: Settings — `capability_token` + `capability_node_b_url` (xnch submodule)

**Files:**
- Modify: `xnch/config.py` (after the exec-agent block ending at line ~169)
- Test: `xnch/tests/test_capability_settings.py` (new)

**Interfaces:**
- Produces: `Settings.capability_token: str` (env `XNCH_CAPABILITY_TOKEN`), `Settings.capability_node_b_url: str` (env `XNCH_CAPABILITY_NODE_B_URL`) — consumed by Tasks 3, 4, 5.

- [ ] **Step 1: Write the failing test**

```python
"""Capability sidecar settings (shared exec+fs token and node-b URL)."""

from __future__ import annotations

from xnch.config import Settings


def test_capability_settings_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.capability_token == ""
    assert s.capability_node_b_url == ""


def test_capability_settings_from_env(monkeypatch) -> None:
    monkeypatch.setenv("XNCH_CAPABILITY_TOKEN", "sekrit")
    monkeypatch.setenv("XNCH_CAPABILITY_NODE_B_URL", "http://192.168.50.2:8090")
    s = Settings(_env_file=None)
    assert s.capability_token == "sekrit"
    assert s.capability_node_b_url == "http://192.168.50.2:8090"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch/tests/test_capability_settings.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'capability_token'`

- [ ] **Step 3: Add settings to `xnch/config.py`**

Insert immediately after the exec-agent settings block (after the line `exec_agent_token: str = ""`, ~line 169):

```python
    # Capability sidecar (merged exec-agent + fs-read-agent)
    capability_token: str = ""
    capability_node_b_url: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch/tests/test_capability_settings.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/config.py xnch/tests/test_capability_settings.py
git -C xnch commit -m "feat: add capability_token + capability_node_b_url settings for merged sidecar"
```

Record the submodule SHA for the superrepo bump commit in Task 11.

---

### Task 3: capability_agent — exec router + app + entrypoint

**Files:**
- Create: `capability_agent/__init__.py`, `capability_agent/app.py`, `capability_agent/__main__.py`, `capability_agent/exec_router.py`
- Test: `capability_agent/tests/__init__.py`, `capability_agent/tests/test_exec_router.py`

**Interfaces:**
- Consumes: `xnch_mcp.exec.local.LocalExecBackend(policy, host)`, `xnch_mcp.exec.policy.load_exec_policy(path)` / `ExecDenied`, `xnch_settings.capability_token` / `exec_agent_token` (Task 2).
- Produces: `capability_agent.app:app` (FastAPI), `capability_agent.exec_router.router` (APIRouter, prefix `/exec`), `capability_agent.exec_router._backend` / `_policy` (module globals, test-monkeypatchable — same pattern as the old sidecars).

- [ ] **Step 1: Create package files**

`capability_agent/__init__.py`:
```python
"""Capability sidecar: merged exec-agent + fs-read-agent (node-b)."""

from capability_agent.app import app

__all__ = ["app"]
```

`capability_agent/exec_router.py`:
```python
"""Governed command execution router (capability sidecar, node-b)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from xnch.config import settings as xnch_settings
from xnch_mcp.exec.local import LocalExecBackend
from xnch_mcp.exec.policy import ExecDenied, load_exec_policy

router = APIRouter(prefix="/exec", tags=["exec"])

_LOCAL_HOST = os.environ.get("XNCH_EXEC_LOCAL_HOST", "node-b")


def _policy_path() -> Path:
    path = xnch_settings.exec_policy_path
    if path.is_file():
        return path
    repo_default = Path(__file__).resolve().parents[2] / "infra/no-k3s/shared/exec-policy.yaml"
    return repo_default if repo_default.is_file() else path


_policy = load_exec_policy(_policy_path())
_backend = LocalExecBackend(_policy, _LOCAL_HOST)


def _verify_token(
    token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    candidates = [
        c for c in (xnch_settings.capability_token, xnch_settings.exec_agent_token) if c
    ]
    if not candidates:
        # Fail CLOSED: an unconfigured token on a 0.0.0.0-bound exec service
        # must be a loud misconfiguration, never silent open access.
        raise HTTPException(status_code=503, detail="capability-agent token not configured")
    if not token or not any(secrets.compare_digest(token, c) for c in candidates):
        raise HTTPException(status_code=401, detail="invalid internal token")


class RunRequest(BaseModel):
    command: str
    cwd: str | None = None


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "host": _LOCAL_HOST, "capability": "exec"}


@router.post("/run")
async def run_command(
    body: RunRequest,
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return await _backend.run(body.command, cwd=body.cwd)
    except ExecDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

`capability_agent/app.py` (imports fs_router which doesn't exist until Task 4 — create it in this task with health only, or write app.py in Task 4; to keep every commit green, create `fs_router.py` now with just the router + health endpoint, and add its endpoints in Task 4):

`capability_agent/fs_router.py` (minimal for this task):
```python
"""Read-only filesystem router (capability sidecar, node-b)."""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(prefix="/fs", tags=["fs"])

_LOCAL_HOST = os.environ.get("XNCH_FS_LOCAL_HOST", "node-b")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "host": _LOCAL_HOST, "capability": "fs"}
```

`capability_agent/app.py`:
```python
"""Capability sidecar — one process for governed exec + read-only fs (node-b)."""

from __future__ import annotations

from fastapi import FastAPI

from capability_agent.exec_router import router as exec_router
from capability_agent.fs_router import router as fs_router

app = FastAPI(title="capability-agent", version="1.0.0")
app.include_router(exec_router)
app.include_router(fs_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "capabilities": "exec,fs"}
```

`capability_agent/__main__.py`:
```python
"""Run the capability sidecar (defaults: 127.0.0.1:8090)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("XNCH_CAPABILITY_BIND", "127.0.0.1")
    port = int(os.environ.get("XNCH_CAPABILITY_PORT", "8090"))
    uvicorn.run("capability_agent.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
```

`capability_agent/tests/__init__.py`: empty.

- [ ] **Step 2: Write exec router tests**

`capability_agent/tests/test_exec_router.py`:
```python
"""Tests for the /exec router: token auth and error mapping."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from capability_agent import exec_router
from xnch_mcp.exec.policy import ExecDenied


class _FakeExecBackend:
    def __init__(self, result: dict[str, Any] | None = None, exc: Exception | None = None) -> None:
        self.result = result or {"host": "node-b", "exit_code": 0, "stdout": "ok"}
        self.exc = exc
        self.calls: list[tuple[str, str | None]] = []

    async def run(self, command: str, *, cwd: str | None = None) -> dict[str, Any]:
        self.calls.append((command, cwd))
        if self.exc:
            raise self.exc
        return self.result


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> _FakeExecBackend:
    backend = _FakeExecBackend()
    monkeypatch.setattr(exec_router, "_backend", backend)
    return backend


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=exec_router.router), base_url="http://test")


async def test_health_open(fake_backend: _FakeExecBackend) -> None:
    async with _client() as client:
        resp = await client.get("/exec/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_run_without_configured_token_503(
    fake_backend: _FakeExecBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exec_router.xnch_settings, "capability_token", "")
    monkeypatch.setattr(exec_router.xnch_settings, "exec_agent_token", "")
    async with _client() as client:
        resp = await client.post("/exec/run", json={"command": "echo hi"})
    assert resp.status_code == 503


async def test_run_invalid_token_401(
    fake_backend: _FakeExecBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exec_router.xnch_settings, "capability_token", "right")
    async with _client() as client:
        resp = await client.post(
            "/exec/run", json={"command": "echo hi"}, headers={"X-Internal-Token": "wrong"}
        )
    assert resp.status_code == 401


async def test_run_capability_token_accepted(
    fake_backend: _FakeExecBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exec_router.xnch_settings, "capability_token", "shared")
    async with _client() as client:
        resp = await client.post(
            "/exec/run",
            json={"command": "echo hi", "cwd": "/tmp"},
            headers={"X-Internal-Token": "shared"},
        )
    assert resp.status_code == 200
    assert resp.json()["exit_code"] == 0
    assert fake_backend.calls == [("echo hi", "/tmp")]


async def test_run_legacy_exec_token_accepted(
    fake_backend: _FakeExecBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exec_router.xnch_settings, "capability_token", "")
    monkeypatch.setattr(exec_router.xnch_settings, "exec_agent_token", "legacy")
    async with _client() as client:
        resp = await client.post(
            "/exec/run", json={"command": "echo hi"}, headers={"X-Internal-Token": "legacy"}
        )
    assert resp.status_code == 200


async def test_run_exec_denied_403(
    fake_backend: _FakeExecBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exec_router, "_backend", _FakeExecBackend(exc=ExecDenied("nope")))
    monkeypatch.setattr(exec_router.xnch_settings, "capability_token", "t")
    async with _client() as client:
        resp = await client.post(
            "/exec/run", json={"command": "rm -rf /"}, headers={"X-Internal-Token": "t"}
        )
    assert resp.status_code == 403


async def test_run_timeout_408(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(exec_router, "_backend", _FakeExecBackend(exc=TimeoutError("slow")))
    monkeypatch.setattr(exec_router.xnch_settings, "capability_token", "t")
    async with _client() as client:
        resp = await client.post(
            "/exec/run", json={"command": "sleep 999"}, headers={"X-Internal-Token": "t"}
        )
    assert resp.status_code == 408


async def test_app_mounts_both_routers() -> None:
    from capability_agent.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/exec/health")).status_code == 200
        assert (await client.get("/fs/health")).status_code == 200
        assert (await client.get("/health")).json()["capabilities"] == "exec,fs"
```

- [ ] **Step 3: Run tests**

Run: `pytest capability_agent/tests/test_exec_router.py -v`
Expected: 8 PASS

- [ ] **Step 4: Run full suite (guards regressions)**

Run: `pytest --tb=short -q`
Expected: green (same as Task 1 baseline).

- [ ] **Step 5: Commit (superrepo)**

```bash
git add capability_agent/
git commit -m "feat: capability_agent sidecar app with /exec router (merged exec-agent)"
```

---

### Task 4: capability_agent — fs router endpoints

**Files:**
- Modify: `capability_agent/fs_router.py` (replace the health-only stub)
- Test: `capability_agent/tests/test_fs_router.py` (new — ported from `fs_read_agent/tests/test_server.py`)

**Interfaces:**
- Consumes: `xnch_mcp.fs.local.LocalFsBackend(policy, host)`, `xnch_mcp.fs.policy.load_fs_policy(path)` / `FsAccessDenied`, `xnch_settings.capability_token` / `fs_agent_token`.
- Produces: `/fs/list`, `/fs/read`, `/fs/stat`, `/fs/exists`, `/fs/glob`, `/fs/health` on `capability_agent.app:app`.

- [ ] **Step 1: Write the failing tests (port from fs_read_agent + token cases)**

`capability_agent/tests/test_fs_router.py`:
```python
"""Tests for the /fs router: read-only endpoints, policy denial, token auth."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from capability_agent import fs_router
from capability_agent.app import app
from xnch_mcp.fs.policy import load_fs_policy


@pytest.fixture
def fs_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "home"
    root.mkdir()
    (root / "hello.txt").write_text("agent-ok")

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        f"""
hosts:
  node-b:
    roots:
      - {root}
deny_globs: []
"""
    )

    monkeypatch.setattr(fs_router.xnch_settings, "capability_token", "shared")
    monkeypatch.setattr(fs_router.xnch_settings, "fs_agent_token", "")
    policy = load_fs_policy(policy_path)
    fs_router._policy = policy
    fs_router._backend = fs_router.LocalFsBackend(policy, "node-b")
    return app


def _client(fs_app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=fs_app), base_url="http://test")


async def test_fs_health_open(fs_app) -> None:
    async with _client(fs_app) as client:
        resp = await client.get("/fs/health")
    assert resp.status_code == 200
    assert resp.json()["capability"] == "fs"


async def test_fs_read(fs_app) -> None:
    async with _client(fs_app) as client:
        resp = await client.get(
            "/fs/read",
            params={"path": "hello.txt"},
            headers={"X-Internal-Token": "shared"},
        )
    assert resp.status_code == 200
    assert "agent-ok" in resp.json()["content"]


async def test_fs_read_invalid_token_401(fs_app) -> None:
    async with _client(fs_app) as client:
        resp = await client.get(
            "/fs/read", params={"path": "hello.txt"}, headers={"X-Internal-Token": "nope"}
        )
    assert resp.status_code == 401


async def test_fs_read_without_configured_token_503(
    fs_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fs_router.xnch_settings, "capability_token", "")
    async with _client(fs_app) as client:
        resp = await client.get("/fs/read", params={"path": "hello.txt"})
    assert resp.status_code == 503


async def test_fs_read_not_found_404(fs_app) -> None:
    async with _client(fs_app) as client:
        resp = await client.get(
            "/fs/read", params={"path": "missing.txt"}, headers={"X-Internal-Token": "shared"}
        )
    assert resp.status_code == 404


async def test_fs_stat_and_exists(fs_app) -> None:
    async with _client(fs_app) as client:
        headers = {"X-Internal-Token": "shared"}
        stat = await client.get("/fs/stat", params={"path": "hello.txt"}, headers=headers)
        exists = await client.get("/fs/exists", params={"path": "hello.txt"}, headers=headers)
        missing = await client.get("/fs/exists", params={"path": "nope.txt"}, headers=headers)
    assert stat.status_code == 200
    assert exists.json()["exists"] is True
    assert missing.json()["exists"] is False


async def test_fs_glob(fs_app) -> None:
    async with _client(fs_app) as client:
        resp = await client.get(
            "/fs/glob", params={"pattern": "*.txt"}, headers={"X-Internal-Token": "shared"}
        )
    assert resp.status_code == 200
    assert any("hello.txt" in str(m) for m in resp.json()["matches"])
```

Note: the exact shape of `/fs/glob` and `/fs/stat` response dicts is whatever `LocalFsBackend` returns — if an assertion above misses (e.g. key is `paths` not `matches`), check `xnch_mcp/fs/local.py` for the return dict and fix the assertion, not the backend.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest capability_agent/tests/test_fs_router.py -v`
Expected: FAIL — 404s (routes not yet defined beyond /fs/health), token 401s.

- [ ] **Step 3: Implement the fs router (port from `fs_read_agent/server.py`, add `/fs` prefix + capability token)**

Replace `capability_agent/fs_router.py` with:

```python
"""Read-only filesystem router (capability sidecar, node-b)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from xnch.config import settings as xnch_settings
from xnch_mcp.fs.local import LocalFsBackend
from xnch_mcp.fs.policy import FsAccessDenied, load_fs_policy

router = APIRouter(prefix="/fs", tags=["fs"])

_LOCAL_HOST = os.environ.get("XNCH_FS_LOCAL_HOST", "node-b")


def _policy_path() -> Path:
    path = xnch_settings.fs_policy_path
    if path.is_file():
        return path
    repo_default = Path(__file__).resolve().parents[2] / "infra/no-k3s/shared/fs-policy.yaml"
    return repo_default if repo_default.is_file() else path


_policy = load_fs_policy(_policy_path())
_backend = LocalFsBackend(_policy, _LOCAL_HOST)


def _verify_token(
    token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    candidates = [
        c for c in (xnch_settings.capability_token, xnch_settings.fs_agent_token) if c
    ]
    if not candidates:
        # Fail CLOSED: unconfigured token on a 0.0.0.0-bound service is a loud
        # misconfiguration, never silent open access.
        raise HTTPException(status_code=503, detail="capability-agent token not configured")
    if not token or not any(secrets.compare_digest(token, c) for c in candidates):
        raise HTTPException(status_code=401, detail="invalid internal token")


def _deny(exc: FsAccessDenied) -> HTTPException:
    return HTTPException(status_code=403, detail=str(exc))


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "host": _LOCAL_HOST, "capability": "fs"}


@router.get("/list")
async def list_dir(
    path: str = Query("."),
    recursive: bool = Query(False),
    max_entries: int = Query(1000, ge=1, le=5000),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.list_dir(path, recursive=recursive, max_entries=max_entries)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/read")
async def read_file(
    path: str = Query(...),
    offset: int = Query(0, ge=0),
    max_bytes: int = Query(2_097_152, ge=1, le=10_485_760),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.read(path, offset=offset, max_bytes=max_bytes)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IsADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/stat")
async def stat_path(
    path: str = Query(...),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.stat(path)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc


@router.get("/exists")
async def exists_path(
    path: str = Query(...),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.exists(path)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc


@router.get("/glob")
async def glob_paths(
    pattern: str = Query(...),
    max_results: int = Query(200, ge=1, le=1000),
    _: None = Depends(_verify_token),
) -> dict[str, Any]:
    try:
        return _backend.glob(pattern, max_results=max_results)
    except FsAccessDenied as exc:
        raise _deny(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest capability_agent/tests/ -v`
Expected: all PASS (exec + fs).

- [ ] **Step 5: Commit**

```bash
git add capability_agent/
git commit -m "feat: capability_agent /fs router (merged fs-read-agent)"
```

---

### Task 5: xnch_mcp — retarget remote clients + capability-first settings fallback

**Files:**
- Modify: `xnch_mcp/exec/remote_client.py`, `xnch_mcp/fs/remote_client.py`, `xnch_mcp/exec/service.py` (~lines 36-40), `xnch_mcp/fs/service.py` (~lines 40-44)
- Test: `xnch_mcp/tests/test_remote_clients.py` (new)

**Interfaces:**
- Consumes: `Settings.capability_node_b_url` / `capability_token` (Task 2).
- Produces: `ExecRemoteClient(base_url, token, timeout, transport=None)` hitting `POST /exec/run`, `GET /exec/health`; `FsRemoteClient` hitting `GET /fs/list|read|stat|exists|glob|health`; `ExecRunService.from_settings` / `FsReadService.from_settings` preferring `capability_node_b_url`+`capability_token` and falling back to legacy `exec_agent_node_b_url`/`exec_agent_token` (or fs equivalents). Zero behavior change until `XNCH_CAPABILITY_NODE_B_URL` is set — that's the migration flip and the rollback path.

- [ ] **Step 1: Write the failing tests**

`xnch_mcp/tests/test_remote_clients.py`:
```python
"""Remote client endpoint paths + capability-first settings fallback."""

from __future__ import annotations

import httpx

from xnch_mcp.exec.remote_client import ExecRemoteClient
from xnch_mcp.exec.service import ExecRunService
from xnch_mcp.fs.remote_client import FsRemoteClient
from xnch_mcp.fs.service import FsReadService


async def test_exec_remote_client_hits_exec_paths() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"exit_code": 0, "stdout": "ok"})

    client = ExecRemoteClient("http://node-b:8090", token="t", transport=httpx.MockTransport(handler))
    result = await client.run("echo hi")
    assert result["exit_code"] == 0
    assert seen == ["/exec/run"]

    await client.health()
    assert seen == ["/exec/run", "/exec/health"]


async def test_fs_remote_client_hits_fs_paths() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"exists": True})

    client = FsRemoteClient("http://node-b:8090", token="t", transport=httpx.MockTransport(handler))
    await client.exists("/tmp/x")
    await client.read("/tmp/x")
    await client.list_dir("/tmp")
    await client.stat("/tmp/x")
    await client.glob("*.txt")
    await client.health()
    assert seen == [
        "/fs/exists",
        "/fs/read",
        "/fs/list",
        "/fs/stat",
        "/fs/glob",
        "/fs/health",
    ]


def test_exec_service_prefers_capability_url() -> None:
    class S:
        exec_policy_path = "/nonexistent/exec-policy.yaml"
        exec_local_host = "node-a"
        capability_node_b_url = "http://192.168.50.2:8090"
        capability_token = "shared"
        exec_agent_node_b_url = "http://192.168.50.2:8004"
        exec_agent_token = "legacy"

    svc = ExecRunService.from_settings(S())
    assert svc._remote["node-b"]._base_url == "http://192.168.50.2:8090"
    assert svc._remote["node-b"]._headers["X-Internal-Token"] == "shared"


def test_exec_service_falls_back_to_legacy_url() -> None:
    class S:
        exec_policy_path = "/nonexistent/exec-policy.yaml"
        exec_local_host = "node-a"
        capability_node_b_url = ""
        capability_token = ""
        exec_agent_node_b_url = "http://192.168.50.2:8004"
        exec_agent_token = "legacy"

    svc = ExecRunService.from_settings(S())
    assert svc._remote["node-b"]._base_url == "http://192.168.50.2:8004"
    assert svc._remote["node-b"]._headers["X-Internal-Token"] == "legacy"


def test_fs_service_prefers_capability_url() -> None:
    class S:
        fs_policy_path = "/nonexistent/fs-policy.yaml"
        fs_local_host = "node-a"
        capability_node_b_url = "http://192.168.50.2:8090"
        capability_token = "shared"
        fs_agent_node_b_url = "http://192.168.50.2:8003"
        fs_agent_token = "legacy"

    svc = FsReadService.from_settings(S())
    assert svc._remote["node-b"]._base_url == "http://192.168.50.2:8090"
    assert svc._remote["node-b"]._headers["X-Internal-Token"] == "shared"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest xnch_mcp/tests/test_remote_clients.py -v`
Expected: FAIL — `TypeError: unexpected keyword 'transport'` and path assertions (`/run` not `/exec/run`).

- [ ] **Step 3: Update `xnch_mcp/exec/remote_client.py`**

```python
"""HTTP client for the exec capability of capability-agent on remote hosts."""

from __future__ import annotations

from typing import Any

import httpx


class ExecRemoteClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Internal-Token": token} if token else {}
        self._timeout = timeout
        self._transport = transport

    async def run(self, command: str, *, cwd: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"command": command}
        if cwd:
            payload["cwd"] = cwd
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        ) as client:
            resp = await client.post("/exec/run", json=payload, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=10.0, transport=self._transport
        ) as client:
            resp = await client.get("/exec/health", headers=self._headers)
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 4: Update `xnch_mcp/fs/remote_client.py`**

Same pattern: add `transport: httpx.AsyncBaseTransport | None = None` to `__init__`, pass `transport=self._transport` into every `httpx.AsyncClient(...)`, and change every path: `/list`→`/fs/list`, `/read`→`/fs/read`, `/stat`→`/fs/stat`, `/exists`→`/fs/exists`, `/glob`→`/fs/glob`, `/health`→`/fs/health`. Method bodies otherwise unchanged.

- [ ] **Step 5: Update `from_settings` in `xnch_mcp/exec/service.py` (lines 36-40)**

Replace:
```python
        remote: dict[str, ExecRemoteClient] = {}
        node_b_url = getattr(settings, "exec_agent_node_b_url", "") or ""
        token = getattr(settings, "exec_agent_token", "") or ""
```
with:
```python
        remote: dict[str, ExecRemoteClient] = {}
        node_b_url = (
            getattr(settings, "capability_node_b_url", "")
            or getattr(settings, "exec_agent_node_b_url", "")
            or ""
        )
        token = (
            getattr(settings, "capability_token", "")
            or getattr(settings, "exec_agent_token", "")
            or ""
        )
```

- [ ] **Step 6: Update `from_settings` in `xnch_mcp/fs/service.py` (lines 40-44) identically**

Replace:
```python
        remote: dict[str, FsRemoteClient] = {}
        node_b_url = getattr(settings, "fs_agent_node_b_url", "") or ""
        token = getattr(settings, "fs_agent_token", "") or ""
```
with:
```python
        remote: dict[str, FsRemoteClient] = {}
        node_b_url = (
            getattr(settings, "capability_node_b_url", "")
            or getattr(settings, "fs_agent_node_b_url", "")
            or ""
        )
        token = (
            getattr(settings, "capability_token", "")
            or getattr(settings, "fs_agent_token", "")
            or ""
        )
```

- [ ] **Step 7: Run new + existing xnch_mcp tests**

Run: `pytest xnch_mcp/tests/ -v`
Expected: all PASS including new `test_remote_clients.py` (6 tests) and pre-existing handler tests (they mock remotes via `AsyncMock`, unaffected).

- [ ] **Step 8: Commit**

```bash
git add xnch_mcp/exec/remote_client.py xnch_mcp/fs/remote_client.py \
        xnch_mcp/exec/service.py xnch_mcp/fs/service.py xnch_mcp/tests/test_remote_clients.py
git commit -m "feat: xnch_mcp remote clients target capability sidecar /exec,/fs with legacy fallback"
```

---

### Task 6: Infra unit + policy allowlist + env docs + runbook

**Files:**
- Create: `infra/no-k3s/node-b/systemd/xnch-capability.service`, `docs/runbooks/capability-sidecar-deploy.md`
- Modify: `infra/no-k3s/shared/exec-policy.yaml` (curl allowlist :8003/:8004 → :8090, lines ~69-70 and ~139), `docs/reference/env-vars.md` (fs/exec agent sections), `docs/reference/mcp-config.md` (same tables)

**Interfaces:**
- Consumes: `capability_agent` package (Tasks 3-4), env `XNCH_CAPABILITY_BIND/PORT/TOKEN`, `XNCH_CAPABILITY_NODE_B_URL` (Task 5 flip).
- Produces: deployable unit + documented cutover procedure for node-b.

- [ ] **Step 1: Create the systemd unit**

`infra/no-k3s/node-b/systemd/xnch-capability.service`:
```ini
[Unit]
Description=Capability Agent — governed exec + read-only fs for Nexi (node-b)
After=network.target

[Service]
Type=simple
User=x-nch
WorkingDirectory=/home/x-nch/xnchSystems
EnvironmentFile=/home/x-nch/.xnch/nexi.env
Environment=PYTHONPATH=/home/x-nch/xnchSystems:/home/x-nch/xnchSystems/xnch
Environment=XNCH_EXEC_LOCAL_HOST=node-b
Environment=XNCH_FS_LOCAL_HOST=node-b
Environment=XNCH_CAPABILITY_BIND=0.0.0.0
Environment=XNCH_CAPABILITY_PORT=8090
ExecStart=/home/x-nch/xnchSystems/nexi/.venv/bin/python -m capability_agent
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Update exec-policy curl allowlist**

In `infra/no-k3s/shared/exec-policy.yaml`, replace `curl http://192.168.50.2:8003` and `curl http://192.168.50.2:8004` entries with `curl http://192.168.50.2:8090`, and `curl http://127.0.0.1:8003` with `curl http://127.0.0.1:8090`. (Keep any other entries untouched.)

- [ ] **Step 3: Update env-var docs**

In `docs/reference/env-vars.md`, replace the "Filesystem agent (fs)" and "Exec agent" section URLs/vars with a merged "Capability agent" section:

```markdown
### Capability agent (merged exec + fs sidecar)

| Variable | Default | Description |
|---|---|---|
| `XNCH_CAPABILITY_BIND` | `127.0.0.1` | sidecar bind address |
| `XNCH_CAPABILITY_PORT` | `8090` | sidecar port (node-b) |
| `XNCH_CAPABILITY_TOKEN` | `""` | shared bearer token (wins over legacy per-agent tokens) |
| `XNCH_CAPABILITY_NODE_B_URL` | `""` | e.g. `http://192.168.50.2:8090`; when set, exec+fs remote clients use it |
| `XNCH_FS_POLICY_PATH` | `~/.xnch/fs-policy.yaml` | read-only FS policy |
| `XNCH_FS_LOCAL_HOST` | `node-a` | node this process serves reads for |
| `XNCH_FS_AGENT_NODE_B_URL` | `http://192.168.50.2:8003` | legacy — used only if capability URL unset |
| `XNCH_FS_AGENT_TOKEN` | `""` | legacy fs token (accepted by /fs router) |
| `XNCH_EXEC_POLICY_PATH` | `~/.xnch/exec-policy.yaml` | governed command policy |
| `XNCH_EXEC_LOCAL_HOST` | `node-a` | node this process runs commands on |
| `XNCH_EXEC_AGENT_NODE_B_URL` | `http://192.168.50.2:8004` | legacy — used only if capability URL unset |
| `XNCH_EXEC_AGENT_TOKEN` | `""` | legacy exec token (accepted by /exec router) |
```

Apply the same change to the two tables in `docs/reference/mcp-config.md` (`XNCH_FS_AGENT_TOKEN` / `XNCH_EXEC_AGENT_TOKEN` rows get a pointer to `XNCH_CAPABILITY_TOKEN`).

- [ ] **Step 4: Write the cutover runbook**

`docs/runbooks/capability-sidecar-deploy.md` — contents (exact):

```markdown
# Capability sidecar deploy (node-b)

Replaces `exec-agent.service` (:8004) and `fs-read-agent.service` (:8003)
with one `xnch-capability.service` on :8090.

## Preconditions
- This repo deployed on node-b with Tasks 2-6 merged (capability_agent package + retargeted clients).
- Port 8090 free on node-b: `ss -ltn | grep 8090` → empty.

## Cutover (node-b)
1. Set the shared token in `/home/x-nch/.xnch/nexi.env`:
   `XNCH_CAPABILITY_TOKEN=<same value as XNCH_EXEC_AGENT_TOKEN>`
2. Install the unit:
   ```
   sudo cp infra/no-k3s/node-b/systemd/xnch-capability.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now xnch-capability
   curl -s http://127.0.0.1:8090/health   # {"status":"ok","capabilities":"exec,fs"}
   ```
3. Old units stay running (dual-run window) until step 5.

## Flip callers (node-a + any xnch_mcp host)
4. In the env of every process running xnch_mcp (xnch gateway env file):
   ```
   XNCH_CAPABILITY_NODE_B_URL=http://192.168.50.2:8090
   XNCH_CAPABILITY_TOKEN=<shared token>
   ```
   Restart the xnch gateway. Verify: `python -m cli mcp test --skip-chat` — exec/fs tool tests pass.

## Decommission (node-b)
5. Stop old units:
   ```
   sudo systemctl disable --now exec-agent fs-read-agent
   ```
6. Update the deployed exec policy allowlist on BOTH nodes (`~/.xnch/exec-policy.yaml`): curl entries :8003/:8004 → :8090.

## Rollback
- Unset `XNCH_CAPABILITY_NODE_B_URL` (or set it empty) and restart the gateway —
  clients fall back to `XNCH_EXEC_AGENT_NODE_B_URL` / `XNCH_FS_AGENT_NODE_B_URL`.
- `sudo systemctl start exec-agent fs-read-agent` (units kept until Phase 1 cleanup is confirmed stable).
```

- [ ] **Step 5: Commit**

```bash
git add infra/no-k3s/node-b/systemd/xnch-capability.service \
        infra/no-k3s/shared/exec-policy.yaml \
        docs/reference/env-vars.md docs/reference/mcp-config.md \
        docs/runbooks/capability-sidecar-deploy.md
git commit -m "feat(infra): xnch-capability unit, policy allowlist, env docs, cutover runbook"
```

- [ ] **Step 6: USER OPS GATE — run the cutover on node-b**

This step is executed by the operator on the real node-b/node-a hosts, following `docs/runbooks/capability-sidecar-deploy.md` exactly (install unit → flip callers → verify `python -m cli mcp test --skip-chat` passes exec/fs tests → stop old units). Do NOT proceed to Task 7 (deletion) until the operator confirms the dual-run verification passed.

---

### Task 7: Delete old sidecar packages

**Files:**
- Delete: `exec_agent/` (whole dir), `fs_read_agent/` (whole dir)
- Modify: any remaining references (see Step 3)

**Interfaces:**
- Consumes: operator confirmation from Task 6 Step 6 that the capability sidecar serves all exec/fs traffic.

- [ ] **Step 1: Verify nothing imports the old packages**

Run: `rg -l "exec_agent|fs_read_agent" --type py | grep -v docs`
Expected: only `exec_agent/` and `fs_read_agent/` themselves (their `__main__.py` import strings). If anything else appears, fix it first.

- [ ] **Step 2: Delete**

```bash
git rm -r exec_agent fs_read_agent
```

- [ ] **Step 3: Clean stale references**

Search and update: `rg -ln "exec-agent.service|fs-read-agent.service|exec_agent|fs_read_agent" docs infra README.md AGENTS.md` — historical review docs under `docs/reviews/` are left untouched; deploy/reference docs get updated to name `xnch-capability.service`. Also remove the now-decommissioned unit files from the repo if the operator confirms they were removed from node-b:

```bash
git rm infra/no-k3s/node-b/systemd/exec-agent.service infra/no-k3s/node-b/systemd/fs-read-agent.service
```

- [ ] **Step 4: Run full suite**

Run: `pytest --tb=short -q`
Expected: green (fs_read_agent's tests were ported to `capability_agent/tests/`; exec coverage was newly written in Task 3).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove exec_agent + fs_read_agent (superseded by capability_agent)"
```

---

### Task 8: AGENTS.md Single-Home Registry

**Files:**
- Modify: `AGENTS.md` (new section after "Multi-Repo Structure")

**Interfaces:** none (documentation consumed by humans + agents).

- [ ] **Step 1: Add the registry**

Insert after the Multi-Repo Structure section in `AGENTS.md`:

```markdown
## Single-Home Registry

| Domain | The ONE home | How everything else uses it |
|---|---|---|
| Policy evaluation | `xnch/policy/` (engine, loader, validator) | nexi pipeline calls it via `XnchClient.check_policies_parallel` (`nexi/pipeline/policy_filter.py`); policy DATA lives per-service in `xnch/policies/`, `nexi/policies/` |
| Security guards (trust tiers, injection/memory guard, sandbox, tokens) | `xnch/security/` | imported by routes/handlers; never merged into `xnch/policy` |
| Runtime episodic memory (L0–L3) | `xnch/memory/` | gateway routes + `xnch_memory_*` tools; routing decided by `~/.xnch/memory-routing.yaml` (`xnch/memory/routing_policy.py`) |
| Curated cross-session knowledge | agentmemory (:3111) | `am_*` MCP tools ONLY; `xnch_memory_store_note` is deprecated for actors in `deprecate_store_note_for` (enforced in `xnch_mcp/handlers/memory.py`) |
| Governed exec + read-only fs | `capability_agent/` (sidecar) + `xnch_mcp/exec|fs` (backends + dispatch) | MCP exec/fs tools → `ExecRunService`/`FsReadService` → sidecar on node-b :8090 |
| Mac-side dispatch worker | `clients/agent-runner/` | launchd; claims from xnch dispatch queue |
| Human CLI | `clients/cli/` | `python -m cli` / `xnch-cli` |
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): single-home registry for policy, security, memory, capabilities"
```

---

### Task 9: Execution boundary audit (investigation → doc)

**Files:**
- Create: `docs/architecture/execution-boundary.md`

**Interfaces:** none (documentation; explicitly NO code moves in this task — any confirmed duplicate becomes a follow-up task proposal inside the doc).

- [ ] **Step 1: Read the candidate overlap points**

Read these files fully and note every function/class and who calls it:
- `xnch/agents/pipeline_runtime.py`, `xnch/agents/pipeline_graph.py`, `xnch/agents/decision_state.py`, `xnch/agents/hitl.py`
- `xnch/jobs/goal_dispatch.py`, `xnch/jobs/workflow_schedule.py`, `xnch/jobs/consolidation.py`
- `nexi/pipeline/run.py`, `nexi/execution/main.py`, `nexi/workflow/executor.py`, `nexi/goal/driver.py`, `nexi/goal/planner.py`, `nexi/proactivity/engine.py`

Use callers/callees lookups (code-review-graph `query_graph` with `callers_of`/`callees_of`, or `rg` for symbol names) for each public function to establish the actual call graph.

- [ ] **Step 2: Write the boundary doc with this exact structure**

```markdown
# Execution Boundary: xnch vs nexi

## The rule
nexi owns DECIDING (the 12-step pipeline that turns a user turn into an action
spec). xnch owns ORCHESTRATING (scheduling crons, dispatching to runners,
HITL approvals, gateway/API surface).

## Verified boundaries
<!-- One row per subsystem: name, owner (xnch|nexi), key file:line, why it
     belongs there, confirmed callers -->

## Confirmed duplicates / overlaps
<!-- Only entries with evidence (same job, two call paths). For each:
     what, where (file:line both sides), proposed single home, blast radius -->

## Proposed follow-ups
<!-- Each confirmed duplicate becomes one proposed move with files touched.
     NO moves are executed as part of Phase 1. -->
```

Primary suspects to adjudicate (verify, don't assume): `xnch/jobs/workflow_schedule.py` vs `nexi/workflow/executor.py` (who triggers workflows?); `xnch/jobs/goal_dispatch.py` vs `nexi/goal/driver.py` (who advances the goal loop?); `xnch/agents/pipeline_runtime.py` vs `nexi/pipeline/run.py` (are these two different pipelines or one duplicated?).

- [ ] **Step 3: Sanity-check every claim in the doc**

For each "Confirmed duplicates" entry, run the cited grep/graph query and confirm the cited lines exist and say what the doc says they say. Fix any drift.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/execution-boundary.md
git commit -m "docs(arch): execution boundary audit — xnch orchestration vs nexi decision pipeline"
```

---

### Task 10: Group clients under `clients/`

**Files:**
- Move: `cli/` → `clients/cli/`, `agent-runner/` → `clients/agent-runner/`
- Modify: `pyproject.toml` (script + includes), `clients/agent-runner/com.xnch.agent-runner.plist` (REPO path note), docs references

**Interfaces:**
- Produces: importable packages `clients.cli`, `clients.agent-runner.xnch_agent_runner`; script `xnch-cli` unchanged as a command name.

- [ ] **Step 1: Move with history**

```bash
mkdir clients
git mv cli clients/cli
git mv agent-runner clients/agent-runner
```

- [ ] **Step 2: Fix package internals**

- `clients/cli/__init__.py` etc. use relative imports already (`from .client import ...`) — verify `rg -n "from cli\.|import cli$" clients/cli` returns nothing (it must all be relative).
- `pyproject.toml`: change `xnch-cli = "cli.main:app"` → `xnch-cli = "clients.cli.main:app"`, and `include = ["cli*"]` → `include = ["clients*"]`.
- `clients/agent-runner/com.xnch.agent-runner.plist`: update the `REPO` placeholder comment if it hardcodes `.../xnchSystems/agent-runner` → `.../xnchSystems/clients/agent-runner`.

- [ ] **Step 3: Update doc references**

Known references to update (from grep during planning): `docs/reference/cli-reference.md`, `docs/reference/mcp-http-api.md`, `docs/reference/index.md`, `docs/runbooks/web-search-deploy.md`, `docs/runbooks/memory-routing-deploy.md`, `docs/runbooks/mcp-bridge-deploy.md`, `docs/deploy.md`, `scripts/reddit/reddit_agent.py` (if it shells out to `python -m cli`). Replace `python -m cli` → `python -m clients.cli`, and agent-runner path mentions → `clients/agent-runner`. Historical `docs/reviews/` and dated `docs/superpowers/plans|specs/` files stay untouched.

- [ ] **Step 4: Verify**

Run: `pytest --tb=short -q && .venv/bin/python -m clients.cli --help`
Expected: suite green; CLI help prints.

Run: `rg -n "python -m cli\b" docs README.md AGENTS.md | grep -v superpowers | grep -v reviews`
Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: group clients (cli, agent-runner) under clients/"
```

---

### Task 11: Final verification + submodule bump

**Files:**
- Modify: superrepo gitlink for `xnch/`

- [ ] **Step 1: Full suite + contract snapshot**

Run: `pytest --tb=short -q`
Expected: green, including `xnch_mcp/tests/test_registry.py` (tool registry — proves no MCP tool signature changed).

- [ ] **Step 2: Bump the xnch submodule gitlink**

```bash
git add xnch
git commit -m "chore(xnch): bump to capability settings for merged sidecar"
```

(Use the submodule SHA recorded in Task 2 Step 5; if more xnch submodule commits accumulated, bump to the latest.)

- [ ] **Step 3: Update the spec status**

In `docs/superpowers/specs/2026-09-11-micro-component-split.md`, mark Phase 1 tasks T1.1–T1.8 done (strike or annotate with completion date). Commit:
```bash
git add docs/superpowers/specs/2026-09-11-micro-component-split.md
git commit -m "docs: mark Phase 1 of micro-component split complete"
```

---

## Post-Plan: What Phase 1 does NOT include (by design)

- Phase 2 memory-service extraction (spec §5.7) — separate plan after Phase 1 soaks.
- The actual node-b cutover commands (Task 6 Step 6) — operator-run, gated by the runbook.
- Any code moves from the Task 9 audit — follow-ups proposed inside the audit doc.
