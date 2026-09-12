"""proactivity_surface_enabled gates the muse proactivity surface."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from xnch_mcp.handlers import memory as mem


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    app = SimpleNamespace(kv_cache=SimpleNamespace(redis_client=None))
    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)
    return app


async def test_surface_disabled_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: False)
    result = await mem._memory_surface(SimpleNamespace(), None, {})
    assert result == []


async def test_surface_enabled_uses_engine(app, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Engine:
        async def get_pending(self) -> list[dict]:
            return [{"type": "test"}]

    monkeypatch.setattr(mem, "_proactivity_enabled", lambda: True)

    created: list = []

    class _EngineFactory:
        def __call__(self, redis) -> _Engine:
            created.append(redis)
            return _Engine()

    import nexi.proactivity.engine as pe

    monkeypatch.setattr(pe, "ProactivityEngine", _EngineFactory())
    result = await mem._memory_surface(app, None, {})
    assert result == [{"type": "test"}]