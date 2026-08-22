"""Tests for tool call parsing."""

import json

from xnch_mcp.tool_loop import (
    merge_tool_system_prompt,
    parse_tool_calls_from_message,
)


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


def test_merge_tool_system_prompt_merges_into_existing_system():
    """vLLM rejects a second system message even at the start — must merge."""
    messages = [
        {"role": "system", "content": "You are Nexi."},
        {"role": "user", "content": "hi"},
    ]
    merged = merge_tool_system_prompt(messages, "Use tools wisely.")
    assert [m["role"] for m in merged] == ["system", "user"]
    assert "Use tools wisely." in merged[0]["content"]
    assert "You are Nexi." in merged[0]["content"]


def test_merge_tool_system_prompt_prepends_when_absent():
    messages = [{"role": "user", "content": "hi"}]
    merged = merge_tool_system_prompt(messages, "Use tools wisely.")
    assert [m["role"] for m in merged] == ["system", "user"]
    assert merged[0]["content"] == "Use tools wisely."


def test_merge_tool_system_prompt_empty_messages():
    merged = merge_tool_system_prompt([], "Use tools wisely.")
    assert merged == [{"role": "system", "content": "Use tools wisely."}]
