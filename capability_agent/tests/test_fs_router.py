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