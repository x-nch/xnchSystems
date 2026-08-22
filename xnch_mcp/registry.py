"""Tool registry — definitions, schemas, and invocation."""

from __future__ import annotations

import time
from typing import Any

from xnch_mcp.auth import max_tier_for_role
from xnch_mcp.context import ActorContext
from xnch_mcp.tool_def import Handler, ToolDef
from xnch_mcp.tiers import ToolTier


_REGISTRY: list[ToolDef] = []


def _register(tool: ToolDef) -> None:
    _REGISTRY.append(tool)


def get_registry() -> list[ToolDef]:
    if not _REGISTRY:
        _load_handlers()
    return list(_REGISTRY)


def _load_handlers() -> None:
    from xnch_mcp.handlers import exec, fs, memory, scraper, session, system, web

    for mod in (system, memory, session, fs, exec, web, scraper):
        for tool in mod.TOOLS:
            _register(tool)


def _actor_may_use_tool(actor_role: str, tool: ToolDef) -> bool:
    if tool.allowed_actors is not None and actor_role not in tool.allowed_actors:
        return False
    return tool.tier <= max_tier_for_role(actor_role)


def _memory_target_for_tool(name: str) -> str | None:
    if name.startswith("xnch_memory_"):
        return "episodic"
    if name.startswith("am_memory_"):
        return "agentmemory"
    return None


def _all_tools() -> list[ToolDef]:
    tools = list(get_registry())
    from xnch_mcp.bridge.pool import get_bridge_pool

    pool = get_bridge_pool()
    if pool is not None and pool.started:
        tools.extend(pool.all_tools())
    return tools


def list_tools_for_actor(actor_role: str) -> list[ToolDef]:
    return [t for t in _all_tools() if _actor_may_use_tool(actor_role, t)]


def tool_openai_schema(tool: ToolDef) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


def list_openai_tools(actor_role: str) -> list[dict[str, Any]]:
    return [tool_openai_schema(t) for t in list_tools_for_actor(actor_role)]


async def invoke_tool(
    app_state: Any,
    actor: ActorContext,
    name: str,
    arguments: dict[str, Any],
    *,
    event_log: Any | None = None,
) -> Any:
    tools = {t.name: t for t in _all_tools()}
    tool = tools.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")

    if not _actor_may_use_tool(actor.actor_role, tool):
        raise PermissionError(
            f"Actor '{actor.actor_role}' cannot invoke tool '{name}'"
        )

    started = time.perf_counter()
    try:
        result = await tool.handler(app_state, actor, arguments)
    except Exception as exc:
        if event_log is not None:
            fail_payload: dict[str, Any] = {
                "tool": name,
                "actor": actor.actor_role,
                "tier": tool.tier.name,
                "error": str(exc),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
            memory_target = _memory_target_for_tool(name)
            if memory_target is not None:
                fail_payload["memory_target"] = memory_target
            event_log.emit(
                actor.trace_id,
                "xnch.mcp",
                "TOOL_CALL_FAILED",
                data=fail_payload,
            )
        raise

    bridge_meta = None
    from xnch_mcp.bridge.pool import get_bridge_pool

    pool = get_bridge_pool()
    if pool is not None:
        bridge_meta = pool.get_meta(name)

    if event_log is not None:
        payload: dict[str, Any] = {
            "tool": name,
            "actor": actor.actor_role,
            "tier": tool.tier.name,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
        memory_target = _memory_target_for_tool(name)
        if memory_target is not None:
            payload["memory_target"] = memory_target
        if bridge_meta is not None:
            payload["bridge"] = True
            payload["mcp_server"] = bridge_meta.server_id
            payload["original_tool"] = bridge_meta.original_name
        event_log.emit(actor.trace_id, "xnch.mcp", "TOOL_CALL", data=payload)
    return result
