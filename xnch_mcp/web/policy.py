"""Web search policy — SearXNG backend configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class WebSearchPolicy:
    enabled: bool
    backend: str
    searxng_url: str
    max_results: int
    max_results_cap: int
    timeout_s: float
    safesearch: int
    engines: tuple[str, ...]
    allowed_actors: frozenset[str]


def load_web_search_policy(path: Path) -> WebSearchPolicy:
    if not path.is_file():
        raise FileNotFoundError(f"web search policy not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    engines = data.get("engines") or []
    actors = data.get("allowed_actors") or ["nexi", "operator"]

    return WebSearchPolicy(
        enabled=bool(data.get("enabled", True)),
        backend=str(data.get("backend", "searxng")),
        searxng_url=str(data.get("searxng_url", "http://127.0.0.1:8888")).rstrip("/"),
        max_results=int(data.get("max_results", 5)),
        max_results_cap=int(data.get("max_results_cap", 10)),
        timeout_s=float(data.get("timeout_s", 15)),
        safesearch=int(data.get("safesearch", 1)),
        engines=tuple(str(e) for e in engines),
        allowed_actors=frozenset(str(a) for a in actors),
    )


def policy_summary(policy: WebSearchPolicy) -> dict[str, Any]:
    return {
        "enabled": policy.enabled,
        "backend": policy.backend,
        "searxng_url": policy.searxng_url,
        "max_results": policy.max_results,
        "engines": list(policy.engines),
        "allowed_actors": sorted(policy.allowed_actors),
    }
