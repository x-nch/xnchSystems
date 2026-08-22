"""Dry-run promotion gate — pure comparison, zero side effects."""
from datetime import UTC, datetime

from xnch_train.evalharness.runner import BaselineReport
from xnch_train.gate.promotion_gate import evaluate_candidate


def _report(**overrides: float) -> BaselineReport:
    values: dict[str, float] = {
        "action_fidelity": 0.90, "rejection_avoidance": 0.80,
        "persona_consistency": 0.85, "tool_call_validity": 0.95,
        "latency_p50_ms": 100.0, "latency_p95_ms": 200.0,
    }
    values.update(overrides)
    return BaselineReport(
        checkpoint_id="ckpt-base", suite_version="v1",
        generated_at=datetime(2026, 8, 20, tzinfo=UTC), **values,
    )


def test_eligible_candidate_gets_proposal() -> None:
    baseline, candidate = _report(), _report()
    candidate.checkpoint_id = "ckpt-cand"
    decision = evaluate_candidate(
        baseline, candidate, epsilon=0.02, regression_bound=0.05,
        serving_bound_pct=10.0, checkpoint_id="ckpt-cand",
    )
    assert decision.eligible
    assert decision.reasons == []
    assert decision.proposal is not None
    assert decision.proposal["type"] == "checkpoint.promotion"
    assert decision.proposal["checkpoint_id"] == "ckpt-cand"


def test_gated_metric_below_epsilon_blocks() -> None:
    decision = evaluate_candidate(
        _report(), _report(tool_call_validity=0.90),
        epsilon=0.02, regression_bound=0.05, serving_bound_pct=10.0,
        checkpoint_id="ckpt-cand",
    )
    assert not decision.eligible
    assert decision.proposal is None
    assert any("tool_call_validity" in r for r in decision.reasons)


def test_regression_over_bound_blocks() -> None:
    decision = evaluate_candidate(
        _report(rejection_avoidance=0.70), _report(rejection_avoidance=0.60),
        epsilon=0.02, regression_bound=0.05, serving_bound_pct=10.0,
        checkpoint_id="ckpt-cand",
    )
    assert not decision.eligible
    assert any("regression" in r for r in decision.reasons)


def test_serving_regression_blocks() -> None:
    decision = evaluate_candidate(
        _report(latency_p95_ms=100.0), _report(latency_p95_ms=130.0),
        epsilon=0.02, regression_bound=0.05, serving_bound_pct=10.0,
        checkpoint_id="ckpt-cand",
    )
    assert not decision.eligible
    assert any("latency" in r.lower() for r in decision.reasons)
