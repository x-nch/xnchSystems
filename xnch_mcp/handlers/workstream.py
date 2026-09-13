"""Gas Town workstream tools — spawn (T2) and status (T0)."""

from __future__ import annotations

import logging
from typing import Any

from xnch_mcp.context import ActorContext
from xnch_mcp.gastown import GastownClient
from xnch_mcp.tiers import ToolTier
from xnch_mcp.tool_def import ToolDef

logger = logging.getLogger(__name__)

_TERMINAL = {"completed", "failed"}


def _client() -> GastownClient:
    from xnch.config import settings

    if not settings.gastown_url:
        raise ValueError("gastown not configured (XNCH_GASTOWN_URL)")
    return GastownClient(settings.gastown_url, token=settings.gastown_token)


async def _spawn(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    title = str(args.get("title", "")).strip()
    goal = str(args.get("goal", "")).strip()
    if not title or not goal:
        raise ValueError("title and goal are required")
    client = _client()
    result = await client.spawn(
        title,
        goal,
        workspace_hint=args.get("workspace_hint"),
        agent_hint=args.get("agent_hint"),
    )
    if getattr(app, "event_log", None) is not None:
        app.event_log.emit("workstream", "gateway", "WORKSTREAM_SPAWNED", data=result)
    return result


async def _status(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    result = await client.status(args.get("workstream_id"))
    pg = getattr(app, "pg_episodic", None)
    if pg is not None:
        for ws in result.get("workstreams", []):
            if ws.get("state") not in _TERMINAL:
                continue
            marker = f"workstream {ws.get('id')} {ws.get('state')}"
            if not await pg.has_identical_recent(marker, hours=24):
                await pg.store_episode(
                    type_="workstream",
                    raw_text=f"{marker}: {ws.get('title', '')}",
                    importance=2.0,
                )
    return result


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_workstream_spawn",
        description="Spawn a Gas Town coding-agent workstream on the Mac (git-backed).",
        tier=ToolTier.T2_EXEC,
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "goal": {"type": "string"},
                "workspace_hint": {"type": "string"},
                "agent_hint": {"type": "string"},
            },
            "required": ["title", "goal"],
        },
        handler=_spawn,
    ),
    ToolDef(
        name="xnch_workstream_status",
        description="List Gas Town workstreams (all, or one by id). Stores terminal outcomes as memory episodes.",
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {"workstream_id": {"type": "string"}},
        },
        handler=_status,
    ),
]