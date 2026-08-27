"""Chat completion with MCP tool loop for nexi_gateway."""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

import httpx

from xnch.config import settings
from xnch.routing.response_sanitize import strip_thinking
from xnch_mcp.bridge.pool import get_bridge_pool
from xnch_mcp.context import ActorContext
from xnch_mcp.registry import invoke_tool, list_openai_tools
from xnch_mcp.tool_loop import (
    assistant_tool_call_message,
    merge_tool_system_prompt,
    parse_tool_calls_from_message,
    tool_result_message,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = int(os.environ.get("XNCH_MCP_MAX_TOOL_ROUNDS", str(settings.mcp_max_tool_rounds)))

# Counteracts small models that "refuse" by describing how to act instead of
# calling a tool. Strong, explicit, and role-model-specific.
_TOOL_SYSTEM_PROMPT = (
    "You are an autonomous agent with access to real tools. "
    "When the user asks you to search the web, look something up, check status, "
    "read a file, or perform any action covered by a tool, CALL the tool "
    "immediately. Do not claim you lack tool access and do not give the user "
    "instructions to do it themselves — you can do it. If a tool call fails, "
    "report the error and try a reasonable alternative."
)

# Small models sometimes ignore tools and answer with prose. If a request
# clearly needs an action and the model produced no tool call, retry once with
# tool_choice="required" to force a real tool round.
_TOOL_ACTION_KEYWORDS = (
    "search", "find", "look up", "lookup", "web", "check", "status", "health",
    "list", "read", "run", "fetch", "query", "current", "latest", "show",
)

# When a request clearly needs a specific tool, force that exact function on
# the retry instead of tool_choice="required" (small models pick the wrong tool
# under a generic "required"). Ordered; first keyword match wins.
_TOOL_FORCE_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("xnch_web_search", ("search", "find", "look up", "lookup", "web", "fetch",
                         "query", "current", "latest", "search engine", "google")),
    ("xnch_status", ("status", "system state")),
    ("xnch_health", ("health", "gateway")),
)


def _force_tool(messages: list[dict[str, Any]]) -> str | None:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            text = msg.get("content")
            if not isinstance(text, str):
                return None
            lowered = text.lower()
            for tool, keywords in _TOOL_FORCE_MAP:
                if any(k in lowered for k in keywords):
                    return tool
            return None
    return None


def _needs_tool(messages: list[dict[str, Any]]) -> bool:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            text = msg.get("content")
            if isinstance(text, str):
                return any(k in text.lower() for k in _TOOL_ACTION_KEYWORDS)
            return False
    return False


def _max_tool_rounds() -> int:
    env = os.environ.get("XNCH_MCP_MAX_TOOL_ROUNDS")
    if env is not None:
        return int(env)
    pool = get_bridge_pool()
    if pool is not None and pool.started and pool.has_enabled_servers:
        return settings.mcp_max_tool_rounds_with_bridge
    return settings.mcp_max_tool_rounds
OPENCODE_GO_BASE = os.environ.get("OPENCODE_GO_BASE_URL", settings.opencode_go_api_url)
OPENCODE_GO_API_KEY = os.environ.get("OPENCODE_GO_API_KEY", settings.opencode_go_api_key)


async def chat_with_tools(
    app_state: Any,
    messages: list[dict[str, Any]],
    model_name: str,
    *,
    session_id: str,
    actor_role: str = "nexi",
    max_rounds: int | None = None,
) -> str:
    """Run LiteLLM chat with MCP tools until the model returns text or rounds exhaust."""
    if max_rounds is None:
        max_rounds = _max_tool_rounds()
    tools = list_openai_tools(actor_role)
    trace_id = str(uuid4())
    actor = ActorContext(actor_role=actor_role, trace_id=trace_id, session_id=session_id)
    headers = {"Content-Type": "application/json"}
    if OPENCODE_GO_API_KEY:
        headers["Authorization"] = f"Bearer {OPENCODE_GO_API_KEY}"

    last_message: dict[str, Any] = {}
    last_tool_result: dict[str, Any] | None = None
    messages = merge_tool_system_prompt(messages, _TOOL_SYSTEM_PROMPT)
    forced = False
    force_answer = False
    prev_tool_sig: str | None = None
    async with httpx.AsyncClient(base_url=OPENCODE_GO_BASE, timeout=120.0) as client:
        for round_idx in range(max_rounds):
            payload: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.2 if (forced or force_answer) else 0.7,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
                if force_answer:
                    # Model repeated a tool call — make it answer with the results.
                    payload["tool_choice"] = "none"
                elif forced:
                    forced_tool = _force_tool(messages)
                    payload["tool_choice"] = (
                        {"type": "function", "function": {"name": forced_tool}}
                        if forced_tool
                        else "required"
                    )

            resp = await client.post(
                "/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            last_message = resp.json()["choices"][0]["message"]
            tool_calls = parse_tool_calls_from_message(last_message)
            if not tool_calls:
                if not forced and round_idx == 0 and tools and _needs_tool(messages):
                    forced = True
                    continue
                return _final_text(last_message, last_tool_result)

            tool_sig = json.dumps(tool_calls, sort_keys=True)
            if tool_sig == prev_tool_sig:
                force_answer = True
            prev_tool_sig = tool_sig

            messages.append(assistant_tool_call_message(tool_calls))
            for call in tool_calls:
                try:
                    result = await invoke_tool(
                        app_state,
                        actor,
                        call["name"],
                        call.get("arguments") or {},
                        event_log=app_state.event_log,
                    )
                except Exception as exc:
                    logger.warning("Tool %s failed: %s", call["name"], exc)
                    result = {"error": str(exc)}
                if call["name"] == "xnch_web_search" and isinstance(result, dict):
                    last_tool_result = result
                messages.append(
                    tool_result_message(call.get("id", call["name"]), call["name"], result)
                )
            logger.info("MCP tool round %d completed (%d calls)", round_idx + 1, len(tool_calls))
            if forced:
                # One-shot forced round: after it runs, make the model answer
                # from the results instead of calling more tools.
                forced = False
                force_answer = True

    return _final_text(last_message, last_tool_result)


def _final_text(last_message: dict[str, Any], last_tool_result: dict[str, Any] | None) -> str:
    text = strip_thinking(last_message.get("content") or "").strip()
    if text:
        return text
    if last_tool_result:
        items = last_tool_result.get("results") or []
        if items:
            top = items[0]
            return (
                f"Top result: {top.get('title', '')} — {top.get('url', '')}"
            )
        return "Search completed but returned no results."
    return "Tool completed but produced no summary."
