"""Tests for the synchronous xnch Goal + HITL promotion client (Task 5).

Uses httpx.MockTransport (part of the already-declared `httpx` dependency)
instead of pytest-httpx, so no new dependency is introduced. The mock
handler captures issued requests so we can assert the promotion proposal was
POSTed to `/policy/verdict`.
"""
from __future__ import annotations

import httpx

from xnch_train.train.goal import GoalClient, claim_goal, emit_promotion_proposal


def _make_transport() -> tuple[httpx.MockTransport, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/goals":
            return httpx.Response(200, json={"goal_id": "g-1"})
        if request.url.path == "/policy/verdict":
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler), captured


def test_goal_claim_and_proposal() -> None:
    transport, captured = _make_transport()
    client = GoalClient(base_url="http://xnch.test", transport=transport)

    gid = claim_goal(client, objective="cycle v1 on ds-1", max_steps=10, lease_owner="xtrain")
    assert gid == "g-1"

    emit_promotion_proposal(client, {"type": "checkpoint.promotion", "checkpoint_id": "ckpt-3"})

    post_requests = [r for r in captured if r.method == "POST"]
    assert len(post_requests) >= 2  # POST /goals, POST /goals/claim, POST /policy/verdict
    assert any(r.url.path == "/policy/verdict" for r in captured)
    verdict = next(r for r in captured if r.url.path == "/policy/verdict")
    assert verdict.method == "POST"
