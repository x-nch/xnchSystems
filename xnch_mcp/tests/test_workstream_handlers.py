"""workstream tools: spawn (T2) + status (T0) with outcome ingestion."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from xnch_mcp.gastown import GastownClient
from xnch_mcp.handlers.workstream import TOOLS
from xnch_mcp.tiers import ToolTier
from xnch_mcp.tool_def import ToolDef


def _defs() -> dict[str, ToolDef]:
    return {t.name: t for t in TOOLS}


def test_tiers() -> None:
    defs = _defs()
    assert defs["xnch_workstream_spawn"].tier is ToolTier.T2_EXEC
    assert defs["xnch_workstream_status"].tier is ToolTier.T0_READ


async def test_spawn_calls_gastown(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list = []

    class _Client:
        async def spawn(self, *a, **kw):
            spawned.append({"title": a[0] if a else None, "goal": a[1] if len(a) > 1 else None, **kw})
            return {"id": "ws-9", "state": "queued"}

    monkeypatch.setattr(
        "xnch_mcp.handlers.workstream.GastownClient",
        lambda *a, **k: _Client(),
    )
    monkeypatch.setattr(
        "xnch.config.settings.gastown_url", "http://mac:7474"
    )
    app = SimpleNamespace(pg_episodic=SimpleNamespace())
    defs = _defs()
    result = await defs["xnch_workstream_spawn"].handler(
        app, None, {"title": "t", "goal": "g"}
    )
    assert result["id"] == "ws-9"
    assert spawned[0]["title"] == "t"


async def test_status_stores_terminal_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: list = []

    class _Pg:
        async def has_identical_recent(self, raw_text: str, hours: int = 24) -> bool:
            return False

        async def store_episode(self, type_, raw_text=None, importance=1.0) -> str:
            stored.append((type_, raw_text))
            return "m-1"

    class _Client:
        async def status(self, workstream_id=None):
            return {"workstreams": [{"id": "ws-1", "state": "completed", "title": "t"}]}

    monkeypatch.setattr(
        "xnch_mcp.handlers.workstream.GastownClient",
        lambda *a, **k: _Client(),
    )
    monkeypatch.setattr(
        "xnch.config.settings.gastown_url", "http://mac:7474"
    )
    app = SimpleNamespace(pg_episodic=_Pg())
    defs = _defs()
    result = await defs["xnch_workstream_status"].handler(app, None, {})
    assert result["workstreams"][0]["state"] == "completed"
    assert stored and stored[0][0] == "workstream"