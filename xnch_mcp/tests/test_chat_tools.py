"""Tests for the nexi chat gateway tool-loop fallback rendering."""

from __future__ import annotations

from xnch_mcp.chat_tools import (
    _extract_local_path,
    _final_text,
    _fmt_tool_result,
    _force_tool,
)


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


def test_extract_local_path_home():
    text = "please check /home/x-nch/PavanKalle_resume.docx"
    assert _extract_local_path(text) == "/home/x-nch/PavanKalle_resume.docx"


def test_extract_local_path_none_for_prose():
    assert _extract_local_path("check the resume please") is None
    assert _extract_local_path("run the status command") is None
    assert _extract_local_path("find exec config") is None


def test_force_tool_routes_concrete_path_to_fs_read():
    msgs = [
        {
            "role": "user",
            "content": "check /home/x-nch/PavanKalle_Cloud_Infra_Platform_Engineer_Resume.docx",
        }
    ]
    assert _force_tool(msgs) == "xnch_fs_read"


def test_force_tool_path_requires_read_verb():
    # A path alone, without a read/check/view intent, should not force fs_read.
    msgs = [{"role": "user", "content": "/home/x-nch/foo.txt details later"}]
    assert _force_tool(msgs) is None


def test_force_tool_falls_back_to_search_keyword():
    msgs = [{"role": "user", "content": "search the web for latest news"}]
    assert _force_tool(msgs) == "xnch_web_search"
