"""proactivity_surface_enabled gates the muse proactivity surface."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from xnch_mcp.handlers import memory as mem


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    app = SimpleNamespace(pg_episodic=_Pg())
    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)
    return app


class _Pg:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def fetch_by_type(self, type_: str, limit: int = 20) -> list[dict]:
        self.calls.append((type_, limit))
        return [{"type": type_, "raw_text": f"{type_} event"}]


async def test_surface_disabled_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: False)
    result = await mem._memory_surface(SimpleNamespace(), None, {})
    assert result == []


async def test_surface_enabled_reads_agent_activity(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)
    result = await mem._memory_surface(app, None, {})
    assert result == [
        {"type": "workstream", "raw_text": "workstream event"},
        {"type": "automation", "raw_text": "automation event"},
    ]


async def test_surface_reads_recent_agent_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Pg:
        async def fetch_by_type(self, type_, limit=20):
            if type_ == "workstream":
                return [{"raw_text": "workstream ws-1 completed", "type": "workstream"}]
            return []

    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)
    app = SimpleNamespace(pg_episodic=_Pg())
    result = await mem._memory_surface(app, None, {})
    assert result and result[0]["raw_text"] == "workstream ws-1 completed"