"""T0 anonymous web search via self-hosted SearXNG (Nexi runtime only)."""

from __future__ import annotations

from typing import Any

from xnch_mcp.context import ActorContext
from xnch_mcp.registry import ToolDef
from xnch_mcp.tiers import ToolTier
from xnch_mcp.web.service import WebSearchService

_WEB_ACTORS = frozenset({"nexi", "operator", "opencode"})


def _web_service(app: Any) -> WebSearchService:
    svc = getattr(app, "web_search_service", None)
    if svc is None:
        raise RuntimeError("web_search_service not initialized on app state")
    return svc


async def _web_search(app: Any, actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    svc = _web_service(app)
    if actor.actor_role not in svc.policy.allowed_actors:
        raise PermissionError(f"actor '{actor.actor_role}' cannot use web search")

    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")

    limit = args.get("limit")
    categories = args.get("categories")
    return await svc.search(
        query,
        limit=int(limit) if limit is not None else None,
        categories=str(categories) if categories else None,
    )


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_web_search",
        description=(
            "Search the public web via self-hosted SearXNG (anonymous metasearch, no commercial API). "
            "Use for current events, release notes, CVEs, and external docs not in the repo. "
            "Prefer crg_* for code structure and doc_* for offline library snippets."
        ),
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (specific; avoid secrets in query text).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default from policy, capped at 10).",
                    "minimum": 1,
                    "maximum": 10,
                },
                "categories": {
                    "type": "string",
                    "description": "Optional SearXNG categories, e.g. 'general' or 'it'.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_web_search,
        allowed_actors=_WEB_ACTORS,
    ),
]
