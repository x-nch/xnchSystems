"""Tests for bridged tool result serialization."""

from mcp.types import CallToolResult, TextContent

from xnch_mcp.bridge.result import serialize_call_result


def test_serialize_json_text():
    result = CallToolResult(content=[TextContent(type="text", text='{"ok": true}')])
    assert serialize_call_result(result) == {"ok": True}


def test_serialize_plain_text():
    result = CallToolResult(content=[TextContent(type="text", text="pong")])
    assert serialize_call_result(result) == "pong"


def test_serialize_error():
    result = CallToolResult(
        content=[TextContent(type="text", text="failed")],
        is_error=True,
    )
    payload = serialize_call_result(result)
    assert payload["error"] is True
