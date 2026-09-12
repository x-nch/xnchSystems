"""Tests for MCP HTTP router token authentication (spec OQ1).

Covers four cases:
- missing token → 401
- wrong token → 401
- valid token → 200
- unset token → back-compat 200 (legacy open behavior)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from xnch.main import app as xnch_app


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.event_log = MagicMock()
    state.event_log.emit = MagicMock()
    state.kv_cache = MagicMock()
    state.kv_cache.ping = AsyncMock(return_value=True)
    state.get_state_version = AsyncMock(return_value="v2")
    state.get_policy_version = AsyncMock(return_value="v1.0")
    state.pg_episodic = MagicMock()
    state.pg_episodic.retrieve_similar = AsyncMock(return_value=[])
    return state


def _client():
    return AsyncClient(
        transport=ASGITransport(app=xnch_app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_missing_token_returns_401(mock_state, monkeypatch):
    xnch_app.state = mock_state
    fake_settings = MagicMock()
    fake_settings.mcp_http_token = "secret-token"
    monkeypatch.setattr("xnch_mcp.http_router.settings", fake_settings)

    async with _client() as client:
        resp = await client.get("/mcp/tools", headers={"X-Actor-Role": "external"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_token_returns_401(mock_state, monkeypatch):
    xnch_app.state = mock_state
    fake_settings = MagicMock()
    fake_settings.mcp_http_token = "secret-token"
    monkeypatch.setattr("xnch_mcp.http_router.settings", fake_settings)

    async with _client() as client:
        resp = await client.get(
            "/mcp/tools",
            headers={"X-Actor-Role": "external", "X-MCP-Token": "wrong"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_returns_200(mock_state, monkeypatch):
    xnch_app.state = mock_state
    fake_settings = MagicMock()
    fake_settings.mcp_http_token = "secret-token"
    monkeypatch.setattr("xnch_mcp.http_router.settings", fake_settings)

    async with _client() as client:
        resp = await client.get(
            "/mcp/tools",
            headers={"X-Actor-Role": "external", "X-MCP-Token": "secret-token"},
        )
    assert resp.status_code == 200
    assert "tools" in resp.json()


@pytest.mark.asyncio
async def test_unset_token_backcompat_200(mock_state, monkeypatch):
    xnch_app.state = mock_state
    fake_settings = MagicMock()
    fake_settings.mcp_http_token = ""
    monkeypatch.setattr("xnch_mcp.http_router.settings", fake_settings)

    async with _client() as client:
        resp = await client.get("/mcp/tools", headers={"X-Actor-Role": "external"})
    assert resp.status_code == 200
    assert "tools" in resp.json()