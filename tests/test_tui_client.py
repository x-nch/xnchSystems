"""Tests for the async TUI client adapter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.tui.client import AsyncXnchClient


@pytest.fixture
def mock_sync_client():
    """Mock XnchCliClient for testing."""
    client = MagicMock()
    client.health.return_value = {"status": "ok", "version": "0.1.0"}
    client.nexi_health.return_value = {"status": "ok"}
    client.system_state.return_value = {
        "system_state_version": "v1",
        "policy_version": "v2",
    }
    client.chat.return_value = {
        "response": "hello",
        "model_used": "gpt-4o",
        "session_id": "test-123",
    }
    client.memory_recall.return_value = [
        {"id": "ep1", "content": "test episode", "similarity": 0.9}
    ]
    client.memory_surface.return_value = []
    client.mcp_tools.return_value = {"tools": [{"name": "test_tool"}], "actor": "nexi"}
    client.mcp_servers.return_value = {"enabled": True, "servers": []}
    client.mcp_call.return_value = {"result": "ok"}
    client.new_session.return_value = "cli-new00000001"
    client.clear_session.return_value = "cli-new00000002"
    client.mint_token.return_value = "jwt.test.token"
    client._load_session_id.return_value = "cli-default"
    return client


@pytest.fixture
def async_client(mock_sync_client):
    """Create AsyncXnchClient with mocked sync client."""
    client = AsyncXnchClient.__new__(AsyncXnchClient)
    client._sync = mock_sync_client
    client.config = MagicMock()
    client.config.actor = "operator"
    client.config.nexi_url = "http://localhost:8000"
    client._stream_client = AsyncMock()
    return client


async def test_health(async_client):
    result = await async_client.health()
    assert result["status"] == "ok"


async def test_nexi_health(async_client):
    result = await async_client.nexi_health()
    assert result["status"] == "ok"


async def test_system_state(async_client):
    result = await async_client.system_state()
    assert "system_state_version" in result


async def test_chat(async_client):
    result = await async_client.chat("hello", session_id="test-123")
    assert result["response"] == "hello"


async def test_memory_recall(async_client):
    results = await async_client.memory_recall("test query")
    assert len(results) == 1
    assert results[0]["id"] == "ep1"


async def test_memory_surface(async_client):
    results = await async_client.memory_surface()
    assert results == []


async def test_mcp_tools(async_client):
    data = await async_client.mcp_tools()
    assert len(data["tools"]) == 1


async def test_mcp_call(async_client):
    result = await async_client.mcp_call("test_tool", {"arg": "val"})
    assert result["result"] == "ok"


async def test_new_session(async_client):
    result = await async_client.new_session()
    assert result == "cli-new00000001"


async def test_clear_session(async_client):
    result = await async_client.clear_session()
    assert result == "cli-new00000002"


async def test_mint_token(async_client):
    result = await async_client.mint_token()
    assert result == "jwt.test.token"


async def test_current_session_id(async_client):
    sid = async_client.current_session_id()
    assert sid == "cli-default"


def _make_async_iter(items):
    """Build an object with __aiter__ for async for loops."""
    it = iter(items)

    class _AsyncIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(it)
            except StopIteration:
                raise StopAsyncIteration

    return _AsyncIter()


async def _test_chat_stream_impl(async_client, lines, on_token=None):
    """Shared helper for chat_stream tests."""
    aiter = _make_async_iter(lines)

    stream_resp = MagicMock()
    stream_resp.raise_for_status = MagicMock()
    stream_resp.aiter_lines = MagicMock(return_value=aiter)

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_resp)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    async_client._stream_client.stream = MagicMock(return_value=stream_ctx)

    return await async_client.chat_stream("hi", on_token=on_token)


async def test_chat_stream(async_client):
    """Test SSE streaming with on_token callback."""
    lines = [
        "data: " + json.dumps({"content": "Hello"}),
        "data: " + json.dumps({"content": " world"}),
        "data: [DONE]",
    ]

    tokens: list[str] = []
    result = await _test_chat_stream_impl(async_client, lines, on_token=tokens.append)

    assert result == "Hello world"
    assert tokens == ["Hello", " world"]


async def test_chat_stream_error(async_client):
    """Test that server errors in SSE raise RuntimeError."""
    lines = [
        "data: " + json.dumps({"error": "something broke"}),
    ]

    with pytest.raises(RuntimeError, match="something broke"):
        await _test_chat_stream_impl(async_client, lines)
