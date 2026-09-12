"""CLI helper utilities."""

from __future__ import annotations

import re
from typing import Any

import httpx

_RECALL_RE = re.compile(
    r"^\s*(?:/recall|recall memory|memory recall)\s+(.+?)\s*$", re.IGNORECASE
)


def join_args(parts: list[str] | None) -> str | None:
    """Join CLI argument tokens into a single string."""
    if not parts:
        return None
    text = " ".join(parts).strip()
    return text or None


def dedupe_memory_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate episode content, keeping the highest-similarity row."""
    best_by_content: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for item in results:
        key = (item.get("content") or "").strip()
        if not key:
            continue
        if key not in best_by_content:
            order.append(key)
            best_by_content[key] = item
            continue
        existing = best_by_content[key]
        if item.get("similarity", 0.0) > existing.get("similarity", 0.0):
            best_by_content[key] = item

    return [best_by_content[key] for key in order]


def parse_recall_intent(text: str) -> str | None:
    """Return the query when text is a recall intent, else None.

    Matches `/recall <query>`, `recall memory <query>`, `memory recall <query>`.
    """
    if not text:
        return None
    match = _RECALL_RE.match(text)
    return match.group(1) if match else None


def format_http_error(exc: httpx.HTTPStatusError) -> str:
    """Human-readable API error including JSON detail when present."""
    detail = exc.response.text
    try:
        body = exc.response.json()
        if isinstance(body.get("detail"), str):
            detail = body["detail"]
        elif body.get("detail") is not None:
            detail = str(body["detail"])
    except Exception:
        pass
    return f"HTTP {exc.response.status_code}: {detail}"


def parse_timer_line(line: str) -> dict[str, str] | None:
    """Parse one `systemctl list-timers --no-legend` row into named fields."""
    parts = [part.strip() for part in line.split("  ") if part.strip()]
    if len(parts) < 5:
        return None
    fields = ("next", "left", "last", "passed", "unit", "activates")
    return {fields[i]: parts[i] for i in range(min(len(parts), len(fields)))}
