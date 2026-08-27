"""Tests for the synchronous training cycle orchestrator (Task 6).

Uses httpx.MockTransport (part of the already-declared `httpx` dependency)
instead of pytest-httpx, so no new dependency is introduced. The mock handler
captures issued requests so we can assert the promotion proposal was POSTed to
`/policy/verdict`.
"""
from __future__ import annotations

import httpx
from pathlib import Path

from xnch_train.train.cycle import run_cycle
from xnch_train.train.goal import GoalClient


def _make_transport() -> tuple[httpx.MockTransport, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/goals":
            return httpx.Response(200, json={"goal_id": "g-1"})
        if request.url.path == "/goals/claim":
            return httpx.Response(200, json={})
        if request.url.path == "/policy/verdict":
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler), captured


def test_cycle_runs_and_proposes_promotion(tmp_path: Path) -> None:
    (tmp_path / "ds").mkdir()
    (tmp_path / "ds" / "records.jsonl").write_text('{"text":"hi"}\n')
    (tmp_path / "ds" / "scrub_manifest.json").write_text('{"version":"1"}')

    transport, captured = _make_transport()
    client = GoalClient(base_url="http://xnch.test", transport=transport)

    ckpt = run_cycle(
        client,
        base_model="b",
        dataset_dir=tmp_path / "ds",
        out_dir=tmp_path / "cycle",
    )

    assert isinstance(ckpt, str)
    assert ckpt.startswith("ckpt-")
    assert any(
        r.method == "POST" and r.url.path == "/policy/verdict" for r in captured
    )
