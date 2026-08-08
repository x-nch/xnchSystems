"""Tests for fs-read-agent HTTP service."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from fs_read_agent import server as agent_server


@pytest.fixture
def agent_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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

    monkeypatch.setenv("XNCH_FS_AGENT_TOKEN", "")
    monkeypatch.setattr(agent_server.xnch_settings, "fs_policy_path", policy_path)
    monkeypatch.setattr(agent_server.xnch_settings, "fs_agent_token", "")

    policy = agent_server.load_fs_policy(policy_path)
    agent_server._policy = policy
    agent_server._backend = agent_server.LocalFsBackend(policy, "node-b")
    return agent_server.app


@pytest.mark.asyncio
async def test_agent_health(agent_app) -> None:
    transport = ASGITransport(app=agent_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_read(agent_app) -> None:
    transport = ASGITransport(app=agent_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/read", params={"path": "hello.txt"})
    assert resp.status_code == 200
    assert "agent-ok" in resp.json()["content"]
