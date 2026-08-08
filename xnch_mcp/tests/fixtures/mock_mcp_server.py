"""Minimal MCP stdio server for bridge integration tests."""

from __future__ import annotations

import json

import anyio
import mcp_types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server


async def _list_tools(
    _ctx: object, _params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="ping_tool",
                description="Return a pong payload.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            ),
            types.Tool(
                name="secret_tool",
                description="Should be blocked by allowlist tests.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]
    )


async def _call_tool(
    _ctx: object, params: types.CallToolRequestParams
) -> types.CallToolResult:
    if params.name == "ping_tool":
        args = params.arguments or {}
        payload = {"pong": True, "message": args.get("message", "")}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload))]
        )
    raise ValueError(f"unknown tool: {params.name}")


def _build_server() -> Server:
    return Server(
        "mock-bridge",
        version="0.0.1",
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
    )


async def _run() -> None:
    server = _build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
