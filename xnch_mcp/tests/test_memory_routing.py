"""Tests for episodic vs agentmemory routing."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from xnch_mcp.context import ActorContext
from xnch_mcp.registry import invoke_tool, list_tools_for_actor


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.pg_episodic = MagicMock()
    app.pg_episodic.store_episode = AsyncMock(return_value="ep-1")
    app.event_log = MagicMock()
    return app


@pytest.mark.asyncio
async def test_nexi_blocked_from_store_note(mock_app):
    actor = ActorContext(actor_role="nexi", trace_id="t1", session_id="s1")
    with pytest.raises(PermissionError, match="am_memory"):
        await invoke_tool(
            mock_app,
            actor,
            "xnch_memory_store_note",
            {"text": "deploy lesson"},
            event_log=mock_app.event_log,
        )
    mock_app.pg_episodic.store_episode.assert_not_awaited()


@pytest.mark.asyncio
async def test_operator_can_store_note(mock_app):
    actor = ActorContext(actor_role="operator", trace_id="t1", session_id="s1")
    result = await invoke_tool(
        mock_app,
        actor,
        "xnch_memory_store_note",
        {"text": "operator note"},
        event_log=mock_app.event_log,
    )
    assert result["status"] == "ok"
    mock_app.pg_episodic.store_episode.assert_awaited_once()


@pytest.mark.asyncio
async def test_nexi_still_has_memory_recall():
    tools = {t.name for t in list_tools_for_actor("nexi")}
    assert "xnch_memory_recall" in tools
    assert "xnch_memory_store_note" in tools


def test_memory_target_audit_field():
    from xnch_mcp.registry import _memory_target_for_tool

    assert _memory_target_for_tool("xnch_memory_recall") == "episodic"
    assert _memory_target_for_tool("am_memory_save") == "agentmemory"
    assert _memory_target_for_tool("xnch_health") is None
