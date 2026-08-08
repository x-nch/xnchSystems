"""HTTP router for MCP tool invocation (mounted on xnch)."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from xnch_mcp.bridge.pool import get_bridge_pool
from xnch_mcp.context import ActorContext
from xnch_mcp.registry import invoke_tool, list_openai_tools, list_tools_for_actor, tool_openai_schema

router = APIRouter(prefix="/mcp", tags=["mcp"])


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


def _actor_from_request(request: Request) -> ActorContext:
    role = request.headers.get("X-Actor-Role", "external")
    trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
    session_id = request.headers.get("X-Session-Id")
    return ActorContext(actor_role=role, trace_id=trace_id, session_id=session_id)


@router.get("/tools")
async def list_tools(request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    tools = list_tools_for_actor(actor.actor_role)
    return {
        "actor": actor.actor_role,
        "tools": [
            {"name": t.name, "description": t.description, "tier": t.tier.name}
            for t in tools
        ],
    }


@router.get("/tools/openai")
async def list_tools_openai(request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    return {"tools": list_openai_tools(actor.actor_role)}


@router.get("/servers")
async def list_bridge_servers(request: Request) -> dict[str, Any]:
    pool = get_bridge_pool()
    if pool is None:
        return {"enabled": False, "servers": []}
    return {"enabled": True, "servers": pool.server_status()}


@router.post("/call")
async def call_tool(body: ToolCallRequest, request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    app = request.app.state
    try:
        result = await invoke_tool(
            app,
            actor,
            body.name,
            body.arguments,
            event_log=app.event_log,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"name": body.name, "result": result}


@router.post("/call/batch")
async def call_tools_batch(
    body: list[ToolCallRequest], request: Request
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for call in body:
        resp = await call_tool(call, request)
        results.append(resp)
    return results
