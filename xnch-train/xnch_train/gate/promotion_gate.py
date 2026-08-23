"""Dry-run promotion gate stub — eligibility math only, zero side effects.

Phase 0 scope (ADR §3): the automated gate logic exists and is testable,
but nothing here touches HITL, weights, or services. The proposal payload
shape defined here is what Phase 1 wires into the standard verdict path.
"""
from typing import Any

from pydantic import BaseModel, Field

from ..evalharness.metrics import serving_ratio
from ..evalharness.runner import BaselineReport

GATED_METRICS: tuple[str, ...] = (
    "action_fidelity", "persona_consistency", "tool_call_validity",
)
SCORED_METRICS: tuple[str, ...] = (
    "action_fidelity", "rejection_avoidance", "persona_consistency", "tool_call_validity",
)


class GateDecision(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    proposal: dict[str, Any] | None = None


def evaluate_candidate(
    baseline: BaselineReport,
    candidate: BaselineReport,
    *,
    epsilon: float,
    regression_bound: float = 0.05,
    serving_bound_pct: float,
    checkpoint_id: str,
) -> GateDecision:
    if baseline.suite_version != candidate.suite_version:
        return GateDecision(eligible=False, reasons=[
            f"suite version mismatch: baseline={baseline.suite_version}"
            f" candidate={candidate.suite_version}"
        ])
    reasons: list[str] = []
    for metric in GATED_METRICS:
        floor = getattr(baseline, metric) - epsilon
        if getattr(candidate, metric) < floor:
            reasons.append(
                f"gated metric {metric}: candidate {getattr(candidate, metric):.3f}"
                f" < incumbent-floor {floor:.3f}"
            )
    for metric in SCORED_METRICS:
        drop = getattr(baseline, metric) - getattr(candidate, metric)
        if drop > regression_bound:
            reasons.append(
                f"metric regression {metric}: drop {drop:.3f} > bound {regression_bound:.3f}"
            )
    ratio = serving_ratio(baseline.latency_p95_ms, candidate.latency_p95_ms)
    if ratio > 1 + serving_bound_pct / 100.0:
        reasons.append(
            f"serving latency p95 ratio {ratio:.2f} exceeds +{serving_bound_pct:.0f}%"
        )
    eligible = not reasons
    proposal: dict[str, Any] | None = None
    if eligible:
        proposal = {
            "type": "checkpoint.promotion",
            "checkpoint_id": checkpoint_id,
            "incumbent": baseline.checkpoint_id,
            "suite_version": candidate.suite_version,
            "metrics": {
                m: getattr(candidate, m) for m in SCORED_METRICS
            } | {"latency_p95_ms": candidate.latency_p95_ms},
            "dry_run": True,
        }
    return GateDecision(eligible=eligible, reasons=reasons, proposal=proposal)
