"""Shared MCP tool definition types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from xnch_mcp.tiers import ToolTier

Handler = Callable[[Any, Any, dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    tier: ToolTier
    input_schema: dict[str, Any]
    handler: Handler
    allowed_actors: frozenset[str] | None = None
