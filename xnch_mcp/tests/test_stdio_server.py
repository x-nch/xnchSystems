"""Tests for the stdio MCP server's gateway HTTP headers (X-MCP-Token auth)."""

from __future__ import annotations

from xnch_mcp import stdio_server


def test_headers_default_no_token(monkeypatch) -> None:
    monkeypatch.setenv("XNCH_ACTOR", "external")
    monkeypatch.delenv("XNCH_MCP_TOKEN", raising=False)
    monkeypatch.delenv("XNCH_MCP_HTTP_TOKEN", raising=False)
    headers = stdio_server._headers()
    assert "X-MCP-Token" not in headers
    assert headers["X-Actor-Role"] == "external"


def test_headers_include_token(monkeypatch) -> None:
    monkeypatch.setenv("XNCH_ACTOR", "hermes")
    monkeypatch.setenv("XNCH_MCP_TOKEN", "s3cret")
    monkeypatch.delenv("XNCH_MCP_HTTP_TOKEN", raising=False)
    headers = stdio_server._headers()
    assert headers["X-Actor-Role"] == "hermes"
    assert headers["X-MCP-Token"] == "s3cret"


def test_headers_fall_back_to_http_token(monkeypatch) -> None:
    monkeypatch.setenv("XNCH_ACTOR", "external")
    monkeypatch.delenv("XNCH_MCP_TOKEN", raising=False)
    monkeypatch.setenv("XNCH_MCP_HTTP_TOKEN", "tok2")
    assert stdio_server._headers()["X-MCP-Token"] == "tok2"


def test_headers_prefer_short_token(monkeypatch) -> None:
    monkeypatch.setenv("XNCH_MCP_TOKEN", "short")
    monkeypatch.setenv("XNCH_MCP_HTTP_TOKEN", "long")
    assert stdio_server._headers()["X-MCP-Token"] == "short"