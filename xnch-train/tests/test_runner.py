"""Incumbent-only baseline run produces the five-number report."""
from datetime import UTC, datetime

from xnch_train.evalharness.client import FakeModelClient
from xnch_train.evalharness.metrics import ActionCase, PersonaProbe, RejectionCase
from xnch_train.evalharness.runner import run_baseline
from xnch_train.evalharness.suites import SUITE_VERSION, EvalSuite


def _suite() -> EvalSuite:
    ts = datetime(2026, 8, 20, tzinfo=UTC)
    return EvalSuite(
        cutoff_ts=ts,
        fidelity=[ActionCase(prompt="deploy", source_ts=ts,
                             action_type="DEPLOY", arguments={"env": "prod"})],
        rejection=[RejectionCase(prompt="risky", source_ts=ts,
                                 blocked_action_type="WIPE", blocked_arguments={})],
        persona=[PersonaProbe(prompt="greet", required_markers=["ready"],
                              forbidden_markers=["sorry"])],
        toolset_prompts=["list pods"],
        bench_prompts=["bench me"],
    )


async def test_run_baseline_scores_all_five() -> None:
    tool_call = '<tool_call>{"name": "DEPLOY", "arguments": {"env": "prod"}}</tool_call>'
    replies = [
        tool_call,
        "ready",
        "ready",
        '<tool_call>{"name": "LIST", "arguments": {}}</tool_call>',
        "pong",
    ]
    report = await run_baseline(FakeModelClient(replies, latency_ms=40.0), _suite())
    assert report.checkpoint_id == "incumbent"
    assert report.suite_version == SUITE_VERSION
    assert report.action_fidelity == 1.0
    assert report.rejection_avoidance == 1.0
    assert report.persona_consistency == 1.0
    assert report.tool_call_validity == 1.0
    assert report.latency_p50_ms == 40.0
    assert report.latency_p95_ms == 40.0
