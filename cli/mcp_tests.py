"""MCP bridge test cases for `xnch-cli mcp test`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cli.client import XnchCliClient


@dataclass(frozen=True)
class McpTestCase:
    name: str
    run: Callable[[XnchCliClient], str]


def _check(name: str, ok: bool, detail: str) -> str:
    if not ok:
        raise AssertionError(detail)
    return detail


MCP_TOOL_TESTS: list[McpTestCase] = [
    McpTestCase(
        "bridge servers",
        lambda c: _check(
            "servers",
            len([s for s in c.mcp_servers(actor_role="nexi")["servers"] if s.get("connected")]) >= 3,
            "expected >=3 connected bridge servers",
        ),
    ),
    McpTestCase(
        "tool count",
        lambda c: _check(
            "tools",
            len(c.mcp_tools(actor_role="nexi")["tools"]) >= 35,
            "expected >=35 tools for nexi",
        ),
    ),
    McpTestCase(
        "xnch_health",
        lambda c: _check(
            "health",
            c.mcp_call("xnch_health", actor_role="nexi")["result"]
            .get("mcp_bridge", {})
            .get("enabled")
            is True,
            "mcp_bridge not enabled",
        ),
    ),
    McpTestCase(
        "crg_list_graph_stats",
        lambda c: _check(
            "crg",
            c.mcp_call("crg_list_graph_stats_tool", actor_role="nexi")["result"].get("status") == "ok",
            "crg_list_graph_stats_tool failed",
        ),
    ),
    McpTestCase(
        "crg_semantic_search",
        lambda c: _check(
            "crg search",
            bool(
                c.mcp_call(
                    "crg_semantic_search_nodes_tool",
                    {"query": "McpBridgePool", "limit": 3},
                    actor_role="nexi",
                )["result"].get("results")
            ),
            "no semantic search results",
        ),
    ),
    McpTestCase(
        "crg_callers_invoke_tool",
        lambda c: _check(
            "crg callers",
            "chat_with_tools"
            in [
                x["name"]
                for x in c.mcp_call(
                    "crg_query_graph_tool",
                    {
                        "pattern": "callers_of",
                        "target": "/home/x-nch/xnchSystems/xnch_mcp/registry.py::invoke_tool",
                    },
                    actor_role="nexi",
                )["result"].get("results", [])
            ],
            "chat_with_tools not in callers",
        ),
    ),
    McpTestCase(
        "am_memory_recall",
        lambda c: _check(
            "agentmemory",
            "results"
            in c.mcp_call(
                "am_memory_recall",
                {"query": "MCP bridge", "limit": 2},
                actor_role="nexi",
            )["result"],
            "am_memory_recall missing results",
        ),
    ),
    McpTestCase(
        "doc_resolve_library",
        lambda c: _check(
            "docs resolve",
            bool(
                c.mcp_call(
                    "doc_resolve-library-id",
                    {"libraryName": "FastAPI", "query": "lifespan"},
                    actor_role="nexi",
                )["result"].get("matches")
            ),
            "doc_resolve-library-id no matches",
        ),
    ),
    McpTestCase(
        "doc_query_docs",
        lambda c: _check(
            "docs query",
            c.mcp_call(
                "doc_query-docs",
                {"libraryId": "/fastapi/fastapi", "query": "lifespan"},
                actor_role="nexi",
            )["result"].get("status")
            == "ok",
            "doc_query-docs failed",
        ),
    ),
    McpTestCase(
        "xnch_web_search",
        lambda c: _check(
            "web search",
            c.mcp_call(
                "xnch_web_search",
                {"query": "vLLM release notes", "limit": 2},
                actor_role="nexi",
            )["result"].get("status")
            == "ok",
            "xnch_web_search failed (is searxng running?)",
        ),
    ),
    McpTestCase(
        "web_search_health",
        lambda c: _check(
            "web search health",
            c.mcp_call("xnch_health", actor_role="nexi")["result"]
            .get("web_search", {})
            .get("enabled")
            is True,
            "web_search not enabled in xnch_health",
        ),
    ),
]


CHAT_TESTS: list[McpTestCase] = [
    McpTestCase(
        "nexi/chat doc tool",
        lambda c: _check(
            "chat doc",
            bool(
                c.chat(
                    "Use doc_query-docs for /fastapi/fastapi query lifespan. One sentence.",
                    session_id=f"cli-mcp-test-doc",
                ).get("response")
            ),
            "empty chat response",
        ),
    ),
    McpTestCase(
        "nexi/chat crg tool",
        lambda c: _check(
            "chat crg",
            any(
                name in c.chat(
                    "Use crg_query_graph_tool callers_of invoke_tool. List names only.",
                    session_id=f"cli-mcp-test-crg",
                ).get("response", "")
                for name in ("chat_with_tools", "call_tool")
            ),
            "crg chat did not mention callers",
        ),
    ),
]
