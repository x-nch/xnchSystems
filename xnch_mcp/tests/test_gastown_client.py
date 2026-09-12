"""GastownClient: spawn/status HTTP shapes."""

from __future__ import annotations

import httpx
import pytest

from xnch_mcp.gastown import GastownClient, GastownError


def _ok(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


async def test_spawn_posts_workstream() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(200, json={"id": "ws-1", "state": "queued"})

    client = GastownClient(
        "http://mac:7474",
        token="t",
        transport=httpx.MockTransport(handler),
    )
    result = await client.spawn("fix login bug", "Fix the login timeout", workspace_hint="xnch")
    assert result["id"] == "ws-1"
    assert seen["path"] == "/api/workstreams"

    body = __import__("json").loads(seen["body"])
    assert body["title"] == "fix login bug"
    assert body["goal"] == "Fix the login timeout"


async def test_status_gets_workstreams() -> None:
    client = GastownClient(
        "http://mac:7474",
        token="t",
        transport=_ok({"workstreams": [{"id": "ws-1", "state": "running"}]}),
    )
    result = await client.status()
    assert result["workstreams"][0]["state"] == "running"


async def test_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = GastownClient(
        "http://mac:7474",
        token="t",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(GastownError):
        await client.status()
