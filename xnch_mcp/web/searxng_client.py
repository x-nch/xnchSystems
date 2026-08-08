"""SearXNG HTTP client."""

from __future__ import annotations

from typing import Any

import httpx

from xnch_mcp.web.policy import WebSearchPolicy


class WebSearchError(RuntimeError):
    """Raised when SearXNG returns an error or is unreachable."""


class SearxngClient:
    def __init__(self, policy: WebSearchPolicy) -> None:
        self._policy = policy

    async def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        categories: str | None = None,
    ) -> dict[str, Any]:
        q = query.strip()
        if not q:
            raise ValueError("query is required")

        max_results = limit or self._policy.max_results
        max_results = min(max_results, self._policy.max_results_cap)

        params: dict[str, Any] = {
            "q": q,
            "format": "json",
            "safesearch": self._policy.safesearch,
        }
        if self._policy.engines:
            params["engines"] = ",".join(self._policy.engines)
        if categories:
            params["categories"] = categories

        url = f"{self._policy.searxng_url}/search"
        async with httpx.AsyncClient(timeout=self._policy.timeout_s) as client:
            try:
                resp = await client.get(url, params=params)
            except httpx.RequestError as exc:
                raise WebSearchError(f"SearXNG unreachable at {self._policy.searxng_url}: {exc}") from exc

        if resp.status_code == 403:
            raise WebSearchError(
                "SearXNG returned 403 — enable json format in settings.yml search.formats"
            )
        if resp.status_code >= 400:
            raise WebSearchError(f"SearXNG HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        results = data.get("results") or []
        trimmed = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content") or item.get("snippet", ""),
                "engine": item.get("engine"),
            }
            for item in results[:max_results]
        ]

        return {
            "status": "ok",
            "query": q,
            "backend": "searxng",
            "result_count": len(trimmed),
            "results": trimmed,
        }

    async def ping(self) -> bool:
        url = f"{self._policy.searxng_url}/healthz"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except httpx.RequestError:
            return False
