"""Offline Context7-style documentation MCP server for Nexi bridge testing.

Mirrors @upstash/context7-mcp tool names and schemas but returns canned
documentation snippets — no API key or network required.
"""

from __future__ import annotations

import json
from typing import Any

import anyio
import mcp_types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

_LIBRARIES: dict[str, dict[str, str]] = {
    "/fastapi/fastapi": {
        "title": "FastAPI",
        "description": "Modern Python web framework for building APIs.",
    },
    "/pydantic/pydantic": {
        "title": "Pydantic",
        "description": "Data validation using Python type hints.",
    },
    "/modelcontextprotocol/python-sdk": {
        "title": "MCP Python SDK",
        "description": "Model Context Protocol SDK for Python.",
    },
    "/berriai/litellm": {
        "title": "LiteLLM",
        "description": "Call 100+ LLM APIs using the OpenAI format.",
    },
    "/kuzudb/kuzu": {
        "title": "Kuzu",
        "description": "Embedded graph database for analytics.",
    },
}

_SNIPPETS: dict[str, list[str]] = {
    "/fastapi/fastapi": [
        "Use lifespan context managers for startup/shutdown instead of deprecated on_event.",
        "Mount routers with app.include_router(router, prefix='/api').",
        "Return Pydantic models directly — FastAPI serializes them to JSON.",
    ],
    "/pydantic/pydantic": [
        "Use model_config = ConfigDict(...) on BaseModel subclasses in v2.",
        "Use Field(default_factory=list) for mutable defaults.",
        "model_dump(mode='json') for HTTP-safe serialization.",
    ],
    "/modelcontextprotocol/python-sdk": [
        "Stdio servers use mcp.server.stdio.stdio_server with Server callbacks.",
        "Clients connect via mcp.client.stdio.stdio_client and ClientSession.",
        "list_tools / call_tool are the primary MCP interaction methods.",
    ],
    "/berriai/litellm": [
        "Proxy OpenAI-compatible requests to /chat/completions.",
        "Set model as provider/model, e.g. openai/gpt-4 or ollama/llama3.",
        "Use streaming with stream=True for token-by-token responses.",
    ],
    "/kuzudb/kuzu": [
        "Open with kuzu.Database(path) and kuzu.Connection(db).",
        "Use Cypher: MATCH (n) RETURN n LIMIT 10.",
        "Only one write connection per database file at a time.",
    ],
}


def _resolve_library_id(arguments: dict[str, Any]) -> dict[str, Any]:
    library_name = str(arguments.get("libraryName", "")).strip().lower()
    query = str(arguments.get("query", "")).strip()
    if not library_name:
        raise ValueError("libraryName is required")

    matches: list[dict[str, str]] = []
    for lib_id, meta in _LIBRARIES.items():
        haystack = f"{meta['title']} {meta['description']} {lib_id}".lower()
        if library_name in haystack or any(
            token in haystack for token in library_name.split() if len(token) > 2
        ):
            matches.append(
                {
                    "libraryId": lib_id,
                    "title": meta["title"],
                    "description": meta["description"],
                    "relevance": "high" if library_name in haystack else "medium",
                }
            )

    if not matches and "fastapi" in library_name:
        matches.append(
            {
                "libraryId": "/fastapi/fastapi",
                "title": "FastAPI",
                "description": _LIBRARIES["/fastapi/fastapi"]["description"],
                "relevance": "high",
            }
        )

    return {
        "source": "docs-test-mcp",
        "query": query,
        "libraryName": library_name,
        "matches": matches,
        "hint": "Use query-docs with libraryId from matches.",
    }


def _query_docs(arguments: dict[str, Any]) -> dict[str, Any]:
    library_id = str(arguments.get("libraryId", "")).strip()
    query = str(arguments.get("query", "")).strip()
    if not library_id:
        raise ValueError("libraryId is required")
    if not query:
        raise ValueError("query is required")

    snippets = _SNIPPETS.get(library_id, [])
    if not snippets:
        meta = _LIBRARIES.get(library_id)
        if meta is None:
            return {
                "source": "docs-test-mcp",
                "libraryId": library_id,
                "query": query,
                "status": "not_found",
                "summary": f"No canned docs for {library_id}. Try resolve-library-id first.",
            }
        snippets = [meta["description"]]

    return {
        "source": "docs-test-mcp",
        "libraryId": library_id,
        "query": query,
        "status": "ok",
        "snippets": snippets,
        "summary": "\n".join(f"- {line}" for line in snippets),
        "note": "Offline test server — not live Context7. Set CONTEXT7_API_KEY for production docs.",
    }


async def _list_tools(
    _ctx: object, _params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="resolve-library-id",
                description=(
                    "[docs-test] Resolve a library name to a Context7-compatible library ID. "
                    "Offline canned catalog for FastAPI, Pydantic, MCP, LiteLLM, Kuzu."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "libraryName": {
                            "type": "string",
                            "description": "Official library name, e.g. FastAPI or Pydantic.",
                        },
                        "query": {
                            "type": "string",
                            "description": "What you are trying to look up.",
                        },
                    },
                    "required": ["query", "libraryName"],
                },
            ),
            types.Tool(
                name="query-docs",
                description=(
                    "[docs-test] Query canned documentation snippets for a library ID. "
                    "Use after resolve-library-id."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "libraryId": {
                            "type": "string",
                            "description": "Library ID from resolve-library-id, e.g. /fastapi/fastapi.",
                        },
                        "query": {
                            "type": "string",
                            "description": "Specific documentation question.",
                        },
                    },
                    "required": ["libraryId", "query"],
                },
            ),
        ]
    )


async def _call_tool(
    _ctx: object, params: types.CallToolRequestParams
) -> types.CallToolResult:
    args = params.arguments or {}
    if params.name == "resolve-library-id":
        payload = _resolve_library_id(args)
    elif params.name == "query-docs":
        payload = _query_docs(args)
    else:
        raise ValueError(f"unknown tool: {params.name}")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, indent=2))]
    )


def _build_server() -> Server:
    return Server(
        "docs-test-mcp",
        version="0.1.0",
        instructions=(
            "Offline Context7-style documentation lookup for Nexi testing. "
            "No API key required."
        ),
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
