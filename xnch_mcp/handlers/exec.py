"""T2 governed command execution (Nexi runtime only)."""

from __future__ import annotations

from typing import Any

from xnch_mcp.context import ActorContext
from xnch_mcp.registry import ToolDef
from xnch_mcp.tiers import ToolTier

_EXEC_ACTORS = frozenset({"nexi", "operator", "admin"})

_HOST_SCHEMA = {
    "type": "string",
    "enum": ["node-a", "node-b"],
    "description": "node-a = gate7, node-b = xnch-core",
}


def _exec_service(app: Any):
    svc = getattr(app, "exec_run_service", None)
    if svc is None:
        raise RuntimeError("exec_run_service not initialized on app state")
    return svc


async def _exec_run(app: Any, actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    host = args.get("host", "node-a")
    command = str(args.get("command", "")).strip()
    cwd = args.get("cwd")
    if not command:
        raise ValueError("command is required")

    result = await _exec_service(app).run(host, command, cwd=cwd)

    if hasattr(app, "event_log") and app.event_log is not None:
        app.event_log.emit(
            actor.trace_id,
            "xnch.mcp",
            "EXEC_RUN",
            data={
                "host": host,
                "command": command,
                "exit_code": result.get("exit_code"),
                "actor": actor.actor_role,
            },
        )
    return result


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_exec_run",
        description=(
            "Run an allowlisted shell command on node-a or node-b (no shell metacharacters; "
            "read-only ops: systemctl status, journalctl, curl, git status, pytest, etc.)."
        ),
        tier=ToolTier.T2_EXEC,
        input_schema={
            "type": "object",
            "properties": {
                "host": _HOST_SCHEMA,
                "command": {
                    "type": "string",
                    "description": "Full command string, must match allowlist prefix for host",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory under /home/x-nch (optional)",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=_exec_run,
        allowed_actors=_EXEC_ACTORS,
    ),
]
