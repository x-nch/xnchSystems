"""Tool call parsing and chat loop for Nexi gateway."""

from __future__ import annotations

import json
import re
from typing import Any

_TOOL_CALL_XML_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)


def parse_tool_calls_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tool calls from OpenAI-style message or qwen3_xml content."""
    calls: list[dict[str, Any]] = []

    if raw_calls := message.get("tool_calls"):
        for tc in raw_calls:
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            args_raw = fn.get("arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError:
                args = {}
            if name:
                calls.append({"name": name, "arguments": args, "id": tc.get("id", name)})
        return calls

    content = message.get("content") or ""
    for match in _TOOL_CALL_XML_RE.finditer(content):
        try:
            payload = json.loads(match.group(1))
            name = payload.get("name") or payload.get("tool")
            if name:
                calls.append({
                    "name": name,
                    "arguments": payload.get("arguments") or payload.get("parameters") or {},
                    "id": name,
                })
        except json.JSONDecodeError:
            continue
    return calls


def tool_result_message(tool_call_id: str, name: str, result: Any) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": json.dumps(result, default=str),
    }


def assistant_tool_call_message(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": c.get("id", c["name"]),
                "type": "function",
                "function": {
                    "name": c["name"],
                    "arguments": json.dumps(c.get("arguments") or {}),
                },
            }
            for c in calls
        ],
    }
