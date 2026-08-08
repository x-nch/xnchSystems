"""Tests for xnch_web_search MCP handler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from xnch_mcp.context import ActorContext
from xnch_mcp.registry import invoke_tool, list_tools_for_actor
from xnch_mcp.web.policy import WebSearchPolicy
from xnch_mcp.web.service import WebSearchService


@pytest.fixture
def mock_app():
    policy = WebSearchPolicy(
        enabled=True,
        backend="searxng",
        searxng_url="http://127.0.0.1:8888",
        max_results=5,
        max_results_cap=10,
        timeout_s=5.0,
        safesearch=1,
        engines=("duckduckgo",),
        allowed_actors=frozenset({"nexi", "operator"}),
    )
    svc = WebSearchService(policy)
    svc.search = AsyncMock(
        return_value={
            "status": "ok",
            "query": "litellm",
            "result_count": 1,
            "results": [{"title": "LiteLLM", "url": "https://litellm.ai", "snippet": "proxy"}],
        }
    )
    app = MagicMock()
    app.web_search_service = svc
    app.event_log = MagicMock()
    return app


@pytest.mark.asyncio
async def test_web_search_registered_for_nexi():
    tools = list_tools_for_actor("nexi")
    assert "xnch_web_search" in {t.name for t in tools}
    assert "xnch_web_search" not in {t.name for t in list_tools_for_actor("external")}


@pytest.mark.asyncio
async def test_web_search_invoke(mock_app):
    actor = ActorContext(actor_role="nexi", trace_id="t1", session_id="s1")
    result = await invoke_tool(
        mock_app,
        actor,
        "xnch_web_search",
        {"query": "litellm release notes", "limit": 3},
        event_log=mock_app.event_log,
    )
    assert result["status"] == "ok"
    assert result["result_count"] == 1
    mock_app.web_search_service.search.assert_awaited_once_with(
        "litellm release notes",
        limit=3,
        categories=None,
    )


@pytest.mark.asyncio
async def test_web_search_blocks_external(mock_app):
    actor = ActorContext(actor_role="external", trace_id="t1", session_id="s1")
    with pytest.raises(PermissionError):
        await invoke_tool(mock_app, actor, "xnch_web_search", {"query": "test"})
