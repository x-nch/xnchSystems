"""Tests for xtrain cycle observability + disk-quota hygiene (Task 7).

Uses httpx.MockTransport (part of the already-declared `httpx` dependency)
instead of pytest-httpx, so no new dependency is introduced. The mock handler
captures issued requests so we can assert the tracer emitted exactly one POST
for each cycle event (begin / step / result).
"""
from __future__ import annotations

import httpx

from xnch_train.train.observability import CycleTracer, GpuPoller
from xnch_train.train.registry import CheckpointRegistry


def _make_transport() -> tuple[httpx.MockTransport, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={})

    return httpx.MockTransport(handler), captured


def test_tracer_emits_cycle_and_step_spans() -> None:
    transport, captured = _make_transport()
    tracer = CycleTracer(
        langfuse_host="http://lf.test",
        public_key="pk",
        secret_key="sk",
        transport=transport,
    )
    tracer.begin("run1")
    tracer.step("train", {"loss": 0.5})
    tracer.result(eligible=True, report_id="r1")
    assert len(captured) == 3
    assert all(r.method == "POST" for r in captured)
    assert all(r.url.path == "/api/public/trace" for r in captured)


def test_quota_warning_returns_bool_and_does_not_raise(tmp_path) -> None:
    reg = CheckpointRegistry(tmp_path / "reg.sqlite")
    assert isinstance(reg.quota_warning(), bool)


def test_gpu_poller_emits_contention_event() -> None:
    transport, captured = _make_transport()
    poller = GpuPoller(langfuse_host="http://lf.test", transport=transport)
    poller.emit({"holder": "vision-media-stack", "kind": "oom"})
    assert len(captured) == 1
    assert captured[0].url.path == "/api/public/trace"
