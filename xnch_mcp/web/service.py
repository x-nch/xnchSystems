"""Web search service — anonymous metasearch via self-hosted SearXNG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xnch_mcp.web.policy import WebSearchPolicy, load_web_search_policy, policy_summary
from xnch_mcp.web.searxng_client import SearxngClient, WebSearchError


class WebSearchService:
    def __init__(self, policy: WebSearchPolicy) -> None:
        self._policy = policy
        self._client = SearxngClient(policy)

    @classmethod
    def from_settings(cls, settings: Any) -> WebSearchService:
        policy_path = Path(settings.web_search_policy_path)
        if not policy_path.is_file():
            repo_default = (
                Path(__file__).resolve().parents[2] / "infra/no-k3s/shared/web-search.example.yaml"
            )
            policy_path = repo_default if repo_default.is_file() else policy_path
        policy = load_web_search_policy(policy_path)
        return cls(policy)

    @property
    def policy(self) -> WebSearchPolicy:
        return self._policy

    def status(self) -> dict[str, Any]:
        return policy_summary(self._policy)

    async def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        categories: str | None = None,
    ) -> dict[str, Any]:
        if not self._policy.enabled:
            raise WebSearchError("web search is disabled in policy")
        if self._policy.backend != "searxng":
            raise WebSearchError(f"unsupported backend: {self._policy.backend}")
        return await self._client.search(query, limit=limit, categories=categories)

    async def ping(self) -> bool:
        if not self._policy.enabled:
            return False
        return await self._client.ping()
