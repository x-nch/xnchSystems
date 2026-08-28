"""Tests for the nexi chat gateway tool-loop fallback rendering."""

from __future__ import annotations

from xnch_mcp.chat_tools import _final_text, _fmt_tool_result


def test_fmt_web_search_results():
    result = {"results": [{"title": "X", "url": "http://x"}], "query": "q"}
    assert _fmt_tool_result(result) == "Top result: X — http://x"


def test_fmt_extracted_fs_content():
    result = {"encoding": "extracted", "content": "Resume text here", "path": "p.doc"}
    out = _fmt_tool_result(result)
    assert "Extracted text:" in out
    assert "Resume text here" in out


def test_fmt_plain_content():
    result = {"content": "hello world", "size": 11}
    assert _fmt_tool_result(result) == "hello world"


def test_fmt_exec_stdout():
    result = {"stdout": "done", "exit_code": 0}
    assert _fmt_tool_result(result) == "done"


def test_fmt_error():
    result = {"error": "boom"}
    assert _fmt_tool_result(result) == "Tool error: boom"


def test_final_text_prefers_model_answer():
    msg = {"content": "The resume shows 3 years of Python."}
    assert _final_text(msg, None) == "The resume shows 3 years of Python."


def test_final_text_strips_thinking():
    msg = {"content": "thinking\n<thinking>internal</thinking>\nFinal summary."}
    out = _final_text(msg, None)
    assert "<thinking>" not in out
    assert "Final summary." in out


def test_final_text_surfaces_tool_result_when_model_empty():
    msg = {"content": ""}
    result = {"encoding": "extracted", "content": "Pavan — Senior Backend Engineer"}
    out = _final_text(msg, result, "xnch_fs_read")
    assert "xnch_fs_read" in out
    assert "Pavan" in out


def test_final_text_no_result_returns_fallback():
    msg = {"content": ""}
    assert _final_text(msg, None) == "Tool completed but produced no summary."
