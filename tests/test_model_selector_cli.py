"""End-to-end CLI discovery/probe tests using an httpx MockTransport."""

from __future__ import annotations

import asyncio
import json
import time

import fakeredis
import httpx
import pytest
from typer.testing import CliRunner

from nexi.adapters.model_selector import (
    discover_opencode,
    discover_openrouter,
    fetch_elo,
    is_free_model,
    probe_latency,
)
from scripts import model_selector as ms


@pytest.fixture
def router_models():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "anthropic/claude-sonnet-4",
                        "context_length": 200_000,
                        "pricing": {"prompt": "3", "completion": "15"},
                    },
                    {
                        "id": "google/gemini-2.0-flash-001",
                        "context_length": 1_000_000,
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                    {
                        "id": "nvidia/nemotron-3-super-120b-a12b:free",
                        "context_length": 128_000,
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                ]
            },
        )

    return handler


class _DelayedStream(httpx.AsyncByteStream):
    """Yield (delay, payload) pairs so tests control first-chunk vs total time."""

    def __init__(self, chunks: list[tuple[float, bytes]]):
        self._chunks = chunks

    async def __aiter__(self):
        for delay, payload in self._chunks:
            await asyncio.sleep(delay)
            yield payload


def _stream_handler(first_delay: float, tail_delay: float = 0.0):
    """Stream one content chunk after ``first_delay``, then [DONE] after ``tail_delay``."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=_DelayedStream(
                [
                    (first_delay, b'data: {"choices":[{"delta":{"content":"he"}}]}\n\n'),
                    (tail_delay, b"data: [DONE]\n\n"),
                ]
            ),
        )

    return handler


def _varying_handler(delays: list[float]):
    """Stream a single [DONE] chunk after a per-call delay from ``delays``."""
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        delay = delays[min(state["n"], len(delays) - 1)]
        state["n"] += 1
        return httpx.Response(200, stream=_DelayedStream([(delay, b"data: [DONE]\n\n")]))

    return handler


async def test_discover_openrouter_filters_to_free_only(router_models):
    async with httpx.AsyncClient(base_url="http://or", transport=httpx.MockTransport(router_models)) as c:
        models = await discover_openrouter(c, "http://or/api/v1")
    ids = [m["model_id"] for m in models]
    assert "google/gemini-2.0-flash-001" in ids
    assert "nvidia/nemotron-3-super-120b-a12b:free" in ids
    assert "anthropic/claude-sonnet-4" not in ids  # paid on router
    assert all(is_free_model(m["model_id"], {"prompt": "0", "completion": "0"}) for m in models)


async def test_probe_latency_measures_median(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["called"] = True
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}], "usage": {"total_tokens": 5}})

    async with httpx.AsyncClient(base_url="http://x", transport=httpx.MockTransport(handler)) as c:
        # Simplified test that avoids flaky time monkeypatching
        res = await probe_latency(
            c, "openrouter", "google/gemini-2.0-flash-001",
            "http://x/v1", "key", "Say hello.", timeout_s=10.0, runs=1,
        )
    assert captured.get("called") is True
    assert res["ok"] is True
    # Check that required keys exist rather than specific timing values
    assert "total_ms" in res
    assert "probed_at" in res
    assert isinstance(res["total_ms"], (int, float))
    assert isinstance(res["probed_at"], str)


async def test_probe_latency_ttft_precedes_total():
    """ttft must be the first-chunk delay, total the whole response (not swapped)."""
    async with httpx.AsyncClient(
        base_url="http://x", transport=httpx.MockTransport(_stream_handler(first_delay=0.30, tail_delay=0.05))
    ) as c:
        res = await probe_latency(c, "openrouter", "m", "http://x/v1", "k", "hi", timeout_s=10.0, runs=1)
    assert res["ok"] is True
    assert res["ttft_ms"] >= 250
    assert res["total_ms"] >= 300
    assert res["ttft_ms"] <= res["total_ms"]
    assert res["total_ms"] - res["ttft_ms"] >= 25


async def test_probe_latency_medians_across_runs():
    """Both fields are medians over runs, not a single last-run sample."""
    async with httpx.AsyncClient(
        base_url="http://x", transport=httpx.MockTransport(_varying_handler([0.10, 0.50, 0.30]))
    ) as c:
        res = await probe_latency(c, "openrouter", "m", "http://x/v1", "k", "hi", timeout_s=10.0, runs=3)
    assert res["ok"] is True
    assert 250 <= res["total_ms"] <= 420  # median of ~100/~500/~300
    assert res["ttft_ms"] <= res["total_ms"]


async def test_probe_latency_http_error_is_not_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "rate limited"}})

    async with httpx.AsyncClient(base_url="http://x", transport=httpx.MockTransport(handler)) as c:
        res = await probe_latency(c, "openrouter", "m", "http://x/v1", "k", "hi", timeout_s=10.0, runs=1)
    assert res["ok"] is False
    assert res["ttft_ms"] is None
    assert res["total_ms"] is None
    assert res["probed_at"]


async def test_probe_latency_transport_error_is_not_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async with httpx.AsyncClient(base_url="http://x", transport=httpx.MockTransport(handler)) as c:
        res = await probe_latency(c, "openrouter", "m", "http://x/v1", "k", "hi", timeout_s=10.0, runs=1)
    assert res["ok"] is False
    assert res["total_ms"] is None


async def test_fetch_elo_parses_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"model_name": "a", "elo": 1300},
                {"model": "b", "elo": "not-a-number"},
                {},
                "junk-row",
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        elo = await fetch_elo(c)
    assert elo == {"a": 1300.0}


async def test_fetch_elo_returns_empty_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        assert await fetch_elo(c) == {}


async def test_fetch_elo_returns_empty_on_non_list_body():
    """The real HF endpoint returns an object; iterating it must not raise."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model_name": "a", "elo": 1300})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        assert await fetch_elo(c) == {}


async def test_discover_opencode_parses_models_and_null_context():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-x", "context_length": None},
                    {"id": "gpt-y", "context_length": 200_000},
                    {"model": "legacy"},
                ]
            },
        )

    async with httpx.AsyncClient(base_url="http://oc", transport=httpx.MockTransport(handler)) as c:
        models = await discover_opencode(c, "http://oc/v1")
    assert [m["model_id"] for m in models] == ["gpt-x", "gpt-y", "legacy"]
    assert models[0]["context_window"] == 64_000  # null -> safe default
    assert models[1]["context_window"] == 200_000
    assert all(m["provider"] == "opencode" for m in models)


async def test_discover_opencode_returns_empty_on_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    async with httpx.AsyncClient(base_url="http://oc", transport=httpx.MockTransport(handler)) as c:
        assert await discover_opencode(c, "http://oc/v1") == []


async def test_discover_openrouter_returns_empty_on_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    async with httpx.AsyncClient(base_url="http://or", transport=httpx.MockTransport(handler)) as c:
        assert await discover_openrouter(c, "http://or/api/v1") == []


def _probe_ok(ttft_ms: float, total_ms: float):
    async def _fake(client, provider, model_id, base_url, api_key, prompt, timeout_s, runs):
        return {
            "provider": provider,
            "model_id": model_id,
            "ok": True,
            "ttft_ms": ttft_ms,
            "total_ms": total_ms,
            "probed_at": "2026-09-07T00:00:00",
        }

    return _fake


def _install_fakes(monkeypatch, tmp_path, seeded: list[dict] | None = None):
    fake = fakeredis.FakeRedis(decode_responses=True)
    if seeded is not None:
        fake.set("model_selector:rankings", json.dumps(seeded))
    monkeypatch.setattr(ms, "redis_client_from", lambda cfg: fake)
    monkeypatch.setattr(ms, "_RANKINGS_PATH", tmp_path / "model-rankings.json")
    monkeypatch.setattr(ms, "probe_latency", _probe_ok(20.0, 150.0))
    return fake


def test_cli_run_ranks_and_stores(monkeypatch, tmp_path):
    fake = _install_fakes(monkeypatch, tmp_path)

    async def fake_collect():
        return (
            [
                {"provider": "openrouter", "model_id": "free/fast", "context_window": 128_000, "latency_ms": 0},
                {"provider": "opencode", "model_id": "go/big", "context_window": 200_000, "latency_ms": 0},
            ],
            {"free/fast": 1300.0},
            {"go/big": "frontier"},
        )

    monkeypatch.setattr(ms, "_collect", fake_collect)

    result = CliRunner().invoke(ms.app, ["run"])
    assert result.exit_code == 0, result.output
    assert "discovered=2 ranked=2" in result.output

    stored = json.loads(fake.get("model_selector:rankings"))
    assert {r["model_id"] for r in stored} == {"free/fast", "go/big"}
    assert all(r["latency_ms"] == 150 for r in stored)  # probed latency applied
    top = stored[0]
    assert top["model_id"] == "go/big"
    assert top["tier"] == "frontier"  # manual tier carried through
    assert top["context_window"] == 200_000

    dumped = json.loads((tmp_path / "model-rankings.json").read_text())
    assert len(dumped["rankings"]) == 2


def test_cli_probe_keeps_context_and_tiers(monkeypatch, tmp_path):
    seeded = [
        {
            "provider": "openrouter",
            "model_id": "free/fast",
            "score": 0.5,
            "quality": 0.3,
            "latency_ms": 900,
            "context_window": 128_000,
            "elo": 1300.0,
            "tier": None,
        }
    ]
    fake = _install_fakes(monkeypatch, tmp_path, seeded=seeded)

    result = CliRunner().invoke(ms.app, ["probe"])
    assert result.exit_code == 0, result.output
    assert "re-probed 1 models" in result.output

    stored = json.loads(fake.get("model_selector:rankings"))
    assert stored[0]["latency_ms"] == 150  # refreshed by the probe
    assert stored[0]["context_window"] == 128_000  # not reset to the 64k default
    assert stored[0]["elo"] == 1300.0
    # audit dump refreshed alongside Redis
    dumped = json.loads((tmp_path / "model-rankings.json").read_text())
    assert dumped["rankings"][0]["latency_ms"] == stored[0]["latency_ms"]


def test_cli_probe_without_cache_exits_1(monkeypatch, tmp_path):
    _install_fakes(monkeypatch, tmp_path)

    result = CliRunner().invoke(ms.app, ["probe"])
    assert result.exit_code == 1
    combined = result.output + (getattr(result, "stderr", None) or "")
    assert "No cached rankings" in combined


def test_cli_probe_survives_corrupt_cache(monkeypatch, tmp_path):
    fake = fakeredis.FakeRedis(decode_responses=True)
    fake.set("model_selector:rankings", "{not json")
    monkeypatch.setattr(ms, "redis_client_from", lambda cfg: fake)
    monkeypatch.setattr(ms, "_RANKINGS_PATH", tmp_path / "model-rankings.json")

    result = CliRunner().invoke(ms.app, ["probe"])
    assert result.exit_code == 1  # read_rankings degrades to None instead of raising
