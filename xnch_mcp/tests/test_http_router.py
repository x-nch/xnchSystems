"""Tests for /mcp HTTP router."""

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


@pytest.mark.asyncio
async def test_list_tools_external(mock_state):
    xnch_app.state = mock_state
    transport = ASGITransport(app=xnch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/mcp/tools", headers={"X-Actor-Role": "external"})
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["tools"]}
    assert "xnch_health" in names
    assert "xnch_memory_store_note" not in names


@pytest.mark.asyncio
async def test_call_health(mock_state):
    xnch_app.state = mock_state
    transport = ASGITransport(app=xnch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/call",
            json={"name": "xnch_health", "arguments": {}},
            headers={"X-Actor-Role": "opencode"},
        )
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "ok"
    mock_state.event_log.emit.assert_called()


@pytest.mark.asyncio
async def test_call_write_blocked_for_external(mock_state):
    xnch_app.state = mock_state
    transport = ASGITransport(app=xnch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/call",
            json={"name": "xnch_memory_store_note", "arguments": {"text": "hi"}},
            headers={"X-Actor-Role": "external"},
        )
    assert resp.status_code == 403
