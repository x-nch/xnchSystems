"""Tests for tool call parsing."""

import json

from xnch_mcp.tool_loop import parse_tool_calls_from_message


def test_parse_openai_tool_calls():
    message = {
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "xnch_memory_recall",
                    "arguments": json.dumps({"query": "nexi"}),
                },
            }
        ],
    }
    calls = parse_tool_calls_from_message(message)
    assert len(calls) == 1
    assert calls[0]["name"] == "xnch_memory_recall"
    assert calls[0]["arguments"]["query"] == "nexi"


def test_parse_xml_tool_call():
    message = {
        "content": '<tool_call>{"name": "xnch_health", "arguments": {}}</tool_call>',
    }
    calls = parse_tool_calls_from_message(message)
    assert len(calls) == 1
    assert calls[0]["name"] == "xnch_health"


def test_plain_text_returns_empty():
    assert parse_tool_calls_from_message({"content": "Hello"}) == []
