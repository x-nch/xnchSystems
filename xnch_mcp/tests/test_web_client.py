"""Tests for SearXNG client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from xnch_mcp.web.policy import WebSearchPolicy
from xnch_mcp.web.searxng_client import SearxngClient, WebSearchError


@pytest.fixture
def policy() -> WebSearchPolicy:
    return WebSearchPolicy(
        enabled=True,
        backend="searxng",
        searxng_url="http://127.0.0.1:8888",
        max_results=5,
        max_results_cap=10,
        timeout_s=5.0,
        safesearch=1,
        engines=("duckduckgo", "brave"),
        allowed_actors=frozenset({"nexi", "operator"}),
    )


@pytest.mark.asyncio
async def test_searxng_search_parses_results(policy: WebSearchPolicy):
    client = SearxngClient(policy)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"title": "A", "url": "https://a.test", "content": "snippet a", "engine": "duckduckgo"},
            {"title": "B", "url": "https://b.test", "content": "snippet b"},
        ]
    }

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("xnch_mcp.web.searxng_client.httpx.AsyncClient", return_value=mock_http):
        result = await client.search("test query", limit=2)

    assert result["status"] == "ok"
    assert result["result_count"] == 2
    assert result["results"][0]["title"] == "A"
    mock_http.get.assert_awaited_once()
    call_kwargs = mock_http.get.await_args
    assert call_kwargs.args[0] == "http://127.0.0.1:8888/search"
    assert call_kwargs.kwargs["params"]["q"] == "test query"
    assert call_kwargs.kwargs["params"]["format"] == "json"
    assert call_kwargs.kwargs["params"]["engines"] == "duckduckgo,brave"


@pytest.mark.asyncio
async def test_searxng_search_403(policy: WebSearchPolicy):
    client = SearxngClient(policy)
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "forbidden"

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("xnch_mcp.web.searxng_client.httpx.AsyncClient", return_value=mock_http):
        with pytest.raises(WebSearchError, match="403"):
            await client.search("test")


@pytest.mark.asyncio
async def test_searxng_search_empty_query(policy: WebSearchPolicy):
    client = SearxngClient(policy)
    with pytest.raises(ValueError, match="query is required"):
        await client.search("  ")
