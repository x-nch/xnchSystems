"""Five gate metrics — pure functions, exact scoring semantics."""
from datetime import UTC, datetime

from xnch_train.evalharness.metrics import (
    ActionCase,
    PersonaProbe,
    RejectionCase,
    action_fidelity,
    argument_f1,
    persona_consistency,
    rejection_avoidance,
    serving_ratio,
    tool_call_validity,
)

TS = datetime(2026, 8, 10, tzinfo=UTC)


def test_argument_f1_exact_partial_and_empty() -> None:
    gold = {"env": "prod", "region": "eu"}
    assert argument_f1({"env": "prod", "region": "eu"}, gold) == 1.0
    assert 0.0 < argument_f1({"env": "prod"}, gold) < 1.0
    assert argument_f1({}, gold) == 0.0


def test_action_fidelity_scores_type_then_args() -> None:
    cases = [ActionCase(prompt="deploy it", source_ts=TS,
                        action_type="DEPLOY", arguments={"env": "prod"})]
    good = 'ok <tool_call>{"name": "DEPLOY", "arguments": {"env": "prod"}}</tool_call>'
    wrong_type = '<tool_call>{"name": "DELETE", "arguments": {"env": "prod"}}</tool_call>'
    wrong_args = '<tool_call>{"name": "DEPLOY", "arguments": {"env": "dev"}}</tool_call>'
    assert action_fidelity([good], cases) == 1.0
    assert action_fidelity([wrong_type], cases) == 0.0
    assert 0.0 < action_fidelity([wrong_args], cases) < 1.0
    assert action_fidelity(["no action here"], cases) == 0.0


def test_rejection_avoidance_rewards_new_behavior() -> None:
    cases = [RejectionCase(prompt="do the risky thing", source_ts=TS,
                           blocked_action_type="DROP_TABLE",
                           blocked_arguments={"table": "users"})]
    repeat = '<tool_call>{"name": "DROP_TABLE", "arguments": {"table": "users"}}</tool_call>'
    alternative = '<tool_call>{"name": "BACKUP", "arguments": {"table": "users"}}</tool_call>'
    assert rejection_avoidance([alternative], cases) == 1.0
    assert rejection_avoidance([repeat], cases) == 0.0


def test_persona_consistency_markers() -> None:
    probes = [PersonaProbe(prompt="greet", required_markers=["direct"],
                           forbidden_markers=["sorry"])]
    assert persona_consistency(["be direct now"], probes) == 1.0
    assert persona_consistency(["so sorry, direct maybe"], probes) == 0.0


def test_tool_call_validity() -> None:
    valid = '<tool_call>{"name": "x", "arguments": {}}</tool_call>'
    malformed = "<tool_call>{oops</tool_call>"
    assert tool_call_validity([valid]) == 1.0
    assert tool_call_validity([malformed]) == 0.0
    assert tool_call_validity(["no call"]) == 0.0
    assert tool_call_validity([valid, malformed]) == 0.5


def test_serving_ratio() -> None:
    assert serving_ratio(100.0, 105.0) == 1.05
    assert serving_ratio(100.0, 90.0) == 0.9
