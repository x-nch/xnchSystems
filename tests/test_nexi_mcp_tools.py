"""Tests for nexi chat MCP tool loop integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from xnch.main import app as xnch_app


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.event_log = MagicMock()
    state.event_log.emit = MagicMock()
    state.kv_cache = MagicMock()
    state.kv_cache.redis_client = MagicMock()
    state.pg_episodic = MagicMock()
    state.pg_episodic.retrieve_similar = AsyncMock(return_value=[])
    state.pg_episodic.fetch_by_type = AsyncMock(return_value=[])
    state.pg_episodic.has_identical_recent = AsyncMock(return_value=False)
    state.pg_episodic.store_episode = AsyncMock(return_value="ep-1")
    state.working_memory = MagicMock()
    state.working_memory.append_turn = AsyncMock()
    state.working_memory.get_turns = AsyncMock(return_value=[])
    state.graph_store = MagicMock()
    state.graph_store.get_entity_by_name = MagicMock(return_value=None)
    state.graph_store.fetch_entities = MagicMock(return_value=[])
    state.relationship_store = MagicMock()
    state.relationship_store.get_relationships = AsyncMock(return_value=[])
    state.sensory_buffer = MagicMock()
    state.sensory_buffer.read_recent = AsyncMock(return_value=[])
    proactivity = MagicMock()
    proactivity.get_pending = AsyncMock(return_value=[])
    state._nexi_proactivity = proactivity
    return state


@pytest.mark.asyncio
@patch("xnch.routes.nexi_gateway.scan_input")
@patch("xnch.routes.nexi_gateway.classify_request")
@patch("xnch_mcp.chat_tools.chat_with_tools")
async def test_chat_uses_tool_loop(mock_chat_tools, mock_classify, mock_scan, mock_state):
    mock_scan.return_value = MagicMock(is_clean=True)
    mock_classify.return_value = MagicMock(model_name="ornith")
    mock_chat_tools.return_value = "Recalled from memory."

    xnch_app.state = mock_state
    transport = ASGITransport(app=xnch_app)
    payload = {"session_id": "sess-mcp", "message": "recall nexi"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/nexi/chat", json=payload)

    assert resp.status_code == 200
    assert resp.json()["response"] == "Recalled from memory."
    mock_chat_tools.assert_awaited_once()
