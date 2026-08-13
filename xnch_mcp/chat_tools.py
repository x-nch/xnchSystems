"""Chat completion with MCP tool loop for nexi_gateway."""

from __future__ import annotations

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


def _max_tool_rounds() -> int:
    env = os.environ.get("XNCH_MCP_MAX_TOOL_ROUNDS")
    if env is not None:
        return int(env)
    pool = get_bridge_pool()
    if pool is not None and pool.started and pool.has_enabled_servers:
        return settings.mcp_max_tool_rounds_with_bridge
    return settings.mcp_max_tool_rounds
LITELLM_BASE = os.environ.get("LITELLM_BASE_URL", settings.litellm_proxy_url)
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", os.environ.get("LITELLM_MASTER_KEY", ""))


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
    headers = {"Authorization": f"Bearer {LITELLM_API_KEY}"} if LITELLM_API_KEY else {}

    last_message: dict[str, Any] = {}
    messages = [{"role": "system", "content": _TOOL_SYSTEM_PROMPT}, *messages]
    async with httpx.AsyncClient(base_url=LITELLM_BASE, timeout=120.0) as client:
        for round_idx in range(max_rounds):
            payload: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.7,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            resp = await client.post(
                "/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            last_message = resp.json()["choices"][0]["message"]
            tool_calls = parse_tool_calls_from_message(last_message)
            if not tool_calls:
                return strip_thinking(last_message.get("content") or "")

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
                messages.append(
                    tool_result_message(call.get("id", call["name"]), call["name"], result)
                )
            logger.info("MCP tool round %d completed (%d calls)", round_idx + 1, len(tool_calls))

    return strip_thinking(last_message.get("content") or "Tool loop limit reached.")
