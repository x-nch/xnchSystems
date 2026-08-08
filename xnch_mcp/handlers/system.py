"""T0 system tools."""

from __future__ import annotations

from typing import Any

from xnch_mcp.context import ActorContext
from xnch_mcp.registry import ToolDef
from xnch_mcp.tiers import ToolTier


async def _health(app: Any, _actor: ActorContext, _args: dict[str, Any]) -> dict[str, Any]:
    redis_ok = await app.kv_cache.ping()
    state_version = await app.get_state_version()
    payload: dict[str, Any] = {
        "status": "ok" if redis_ok else "degraded",
        "redis": "ok" if redis_ok else "unavailable",
        "state_version": state_version,
        "version": "0.1.0",
    }
    bridge = getattr(app, "mcp_bridge", None)
    if bridge is not None:
        payload["mcp_bridge"] = {
            "enabled": True,
            "tool_count": len(bridge.all_tools()),
            "servers": bridge.server_status(),
        }
    else:
        payload["mcp_bridge"] = {"enabled": False, "servers": []}
    web_svc = getattr(app, "web_search_service", None)
    if web_svc is not None:
        payload["web_search"] = web_svc.status()
    return payload


async def _status(app: Any, _actor: ActorContext, _args: dict[str, Any]) -> dict[str, Any]:
    state_version = await app.get_state_version()
    policy_version = await app.get_policy_version()
    return {
        "system_state_version": state_version,
        "policy_version": policy_version,
    }


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_health",
        description="Check xnch service health including Redis connectivity.",
        tier=ToolTier.T0_READ,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_health,
    ),
    ToolDef(
        name="xnch_status",
        description="Return system_state_version and policy_version.",
        tier=ToolTier.T0_READ,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_status,
    ),
]
