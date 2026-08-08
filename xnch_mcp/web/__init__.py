"""Anonymous web search policy and SearXNG client."""

from xnch_mcp.web.policy import WebSearchPolicy, load_web_search_policy
from xnch_mcp.web.service import WebSearchService

__all__ = ["WebSearchPolicy", "WebSearchService", "load_web_search_policy"]
