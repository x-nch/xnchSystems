"""MCP stdio server — thin client over xnch HTTP /mcp endpoints."""

from __future__ import annotations

import json
import os
from typing import Any

import anyio
import httpx
import mcp_types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from xnch_mcp.auth import actor_from_env
from xnch_mcp.registry import get_registry, list_tools_for_actor


def _base_url() -> str:
    return os.environ.get("XNCH_BASE_URL", "http://127.0.0.1:8001").rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "X-Actor-Role": actor_from_env(),
        "Content-Type": "application/json",
    }


async def _http_call(name: str, arguments: dict[str, Any]) -> Any:
    async with httpx.AsyncClient(base_url=_base_url(), timeout=120.0) as client:
        resp = await client.post(
            "/mcp/call",
            json={"name": name, "arguments": arguments},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("result")


def _build_server() -> Server:
    actor_role = actor_from_env()
    tools = list_tools_for_actor(actor_role)
    # Ensure registry loaded
    get_registry()

    async def list_tools_handler(
        _ctx: Any, _params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        mcp_tools = [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.input_schema,
            )
            for t in tools
        ]
        return types.ListToolsResult(tools=mcp_tools)

    async def call_tool_handler(
        _ctx: Any, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        try:
            args = params.arguments or {}
            result = await _http_call(params.name, args)
            text = json.dumps(result, indent=2, default=str)
            return types.CallToolResult(content=[types.TextContent(type="text", text=text)])
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"HTTP {exc.response.status_code}: {detail}")],
                isError=True,
            )
        except Exception as exc:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=str(exc))],
                isError=True,
            )

    return Server(
        "xnch",
        version="0.1.0",
        instructions="XNCH control plane tools — memory, health, session pipeline.",
        on_list_tools=list_tools_handler,
        on_call_tool=call_tool_handler,
    )


async def _run() -> None:
    server = _build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
