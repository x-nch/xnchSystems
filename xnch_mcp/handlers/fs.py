"""T0 read-only filesystem tools (Nexi runtime only)."""

from __future__ import annotations

from typing import Any

from xnch_mcp.context import ActorContext
from xnch_mcp.registry import ToolDef
from xnch_mcp.tiers import ToolTier

_FS_ACTORS = frozenset({"nexi", "operator", "admin"})

_HOST_SCHEMA = {
    "type": "string",
    "enum": ["node-a", "node-b"],
    "description": "node-a = gate7 (192.168.50.1), node-b = inference host (192.168.50.2)",
}


def _fs_service(app: Any):
    svc = getattr(app, "fs_read_service", None)
    if svc is None:
        raise RuntimeError("fs_read_service not initialized on app state")
    return svc


async def _fs_list(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    host = args.get("host", "node-a")
    path = args.get("path", ".")
    recursive = bool(args.get("recursive", False))
    return await _fs_service(app).list_dir(host, path, recursive=recursive)


async def _fs_read(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    host = args.get("host", "node-a")
    path = args["path"]
    offset = int(args.get("offset", 0))
    max_bytes = args.get("max_bytes")
    return await _fs_service(app).read(
        host,
        path,
        offset=offset,
        max_bytes=int(max_bytes) if max_bytes is not None else None,
    )


async def _fs_stat(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    return await _fs_service(app).stat(args.get("host", "node-a"), args["path"])


async def _fs_exists(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    return await _fs_service(app).exists(args.get("host", "node-a"), args["path"])


async def _fs_glob(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    return await _fs_service(app).glob(args.get("host", "node-a"), args["pattern"])


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_fs_list",
        description="List files and directories on node-a (gate7) or node-b (read-only).",
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "host": _HOST_SCHEMA,
                "path": {"type": "string", "description": "Path under /home/x-nch (e.g. xnchSystems/xnch/main.py)"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_fs_list,
        allowed_actors=_FS_ACTORS,
    ),
    ToolDef(
        name="xnch_fs_read",
        description="Read a file from node-a or node-b (read-only, truncated above size cap).",
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "host": _HOST_SCHEMA,
                "path": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "max_bytes": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_fs_read,
        allowed_actors=_FS_ACTORS,
    ),
    ToolDef(
        name="xnch_fs_stat",
        description="File or directory metadata on node-a or node-b.",
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "host": _HOST_SCHEMA,
                "path": {"type": "string"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_fs_stat,
        allowed_actors=_FS_ACTORS,
    ),
    ToolDef(
        name="xnch_fs_exists",
        description="Check whether a path exists on node-a or node-b.",
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "host": _HOST_SCHEMA,
                "path": {"type": "string"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_fs_exists,
        allowed_actors=_FS_ACTORS,
    ),
    ToolDef(
        name="xnch_fs_glob",
        description="Glob files under allowed roots on node-a or node-b.",
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "host": _HOST_SCHEMA,
                "pattern": {"type": "string", "description": "e.g. **/*.service"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        handler=_fs_glob,
        allowed_actors=_FS_ACTORS,
    ),
]
