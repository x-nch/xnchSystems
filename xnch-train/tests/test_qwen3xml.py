"""qwen3_xml tool-call parsing (port of the serving-side format)."""
from xnch_train.evalharness.qwen3xml import parse_tool_calls


def test_parses_single_call() -> None:
    text = 'thinking… <tool_call>{"name": "deploy", "arguments": {"env": "prod"}}</tool_call>'
    calls = parse_tool_calls(text)
    assert calls == [{"name": "deploy", "arguments": {"env": "prod"}}]


def test_parses_multiple_and_tolerates_tool_key() -> None:
    text = (
        '<tool_call>{"tool": "a", "parameters": {"x": 1}}</tool_call>\n'
        '<tool_call>not json</tool_call>\n'
        '<tool_call>{"name": "b", "arguments": {}}</tool_call>'
    )
    calls = parse_tool_calls(text)
    assert [c["name"] for c in calls] == ["a", "b"]


def test_no_calls_returns_empty() -> None:
    assert parse_tool_calls("plain prose") == []
