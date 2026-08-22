"""qwen3_xml tool-call parser.

Ported from xnch_mcp/tool_loop.py (same wire format the incumbent serves);
kept local because cross-package imports are forbidden by convention.
"""
import json
import re
from typing import Any

_TOOL_CALL_XML_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _TOOL_CALL_XML_RE.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        name = payload.get("name") or payload.get("tool")
        if not name:
            continue
        arguments = payload.get("arguments") or payload.get("parameters") or {}
        calls.append({"name": str(name), "arguments": arguments})
    return calls
