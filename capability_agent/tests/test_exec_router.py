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
    from capability_agent.app import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


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