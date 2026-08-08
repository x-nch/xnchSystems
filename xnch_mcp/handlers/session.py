"""T2 session pipeline tool."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from xnch_mcp.context import ActorContext
from xnch_mcp.registry import ToolDef
from xnch_mcp.tiers import ToolTier


async def _session_run(app: Any, actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    raw_input = str(args.get("input", "")).strip()
    if not raw_input:
        raise ValueError("input is required")
    priority = str(args.get("priority", "NORMAL")).upper()

    from xnch.routes.session import SessionInitRequest, session_init

    body = SessionInitRequest(
        auth_token=f"actor:{actor.actor_role}",
        raw_input=raw_input,
        input_type="TEXT",
        priority=priority,
        source_system="xnch-mcp",
        trace_id=actor.trace_id,
        idempotency_key=str(uuid4()),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=app))
    return await session_init(body, request)  # type: ignore[arg-type]


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_session_run",
        description="Run the governed decision pipeline (/session/init) for an intent.",
        tier=ToolTier.T2_EXEC,
        input_schema={
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Intent or command"},
                "priority": {"type": "string", "enum": ["NORMAL", "CRITICAL"], "default": "NORMAL"},
            },
            "required": ["input"],
            "additionalProperties": False,
        },
        handler=_session_run,
    ),
]
