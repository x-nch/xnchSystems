"""Serialize MCP CallToolResult for HTTP / chat tool loop."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import CallToolResult


def serialize_call_result(result: CallToolResult) -> Any:
    """Convert MCP tool result to JSON-friendly value for xnch_mcp.invoke_tool."""
    if result.structured_content is not None:
        payload: Any = result.structured_content
    elif result.content:
        texts = [block.text for block in result.content if hasattr(block, "text") and block.text]
        if len(texts) == 1:
            text = texts[0]
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text
        elif texts:
            payload = texts
        else:
            payload = result.model_dump(mode="json")
    else:
        payload = result.model_dump(mode="json")

    if result.is_error:
        if isinstance(payload, dict):
            return {"error": True, **payload}
        return {"error": True, "message": payload}
    return payload
