"""Tests for offline docs test MCP server."""

from docs_test_mcp.server import _query_docs, _resolve_library_id


def test_resolve_library_id_fastapi():
    result = _resolve_library_id(
        {"libraryName": "FastAPI", "query": "lifespan startup"}
    )
    assert result["matches"]
    assert result["matches"][0]["libraryId"] == "/fastapi/fastapi"


def test_query_docs_returns_snippets():
    result = _query_docs(
        {
            "libraryId": "/pydantic/pydantic",
            "query": "Field default_factory",
        }
    )
    assert result["status"] == "ok"
    assert any("default_factory" in s for s in result["snippets"])


def test_query_docs_unknown_library():
    result = _query_docs(
        {"libraryId": "/unknown/lib", "query": "anything"}
    )
    assert result["status"] == "not_found"
