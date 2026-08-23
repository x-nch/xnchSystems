"""Suite versioning and the mandatory temporal train/eval split."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xnch_train.evalharness.metrics import ActionCase, PersonaProbe, RejectionCase
from xnch_train.evalharness.suites import SUITE_VERSION, EvalSuite, load_suite, temporal_split_ok

TS_CUTOFF = datetime(2026, 8, 15, tzinfo=UTC)


def _suite(cutoff: datetime = TS_CUTOFF, case_ts: datetime | None = None) -> EvalSuite:
    ts = case_ts or cutoff
    return EvalSuite(
        cutoff_ts=cutoff,
        fidelity=[ActionCase(prompt="p", source_ts=ts, action_type="A", arguments={})],
        rejection=[RejectionCase(prompt="q", source_ts=ts,
                                 blocked_action_type="B", blocked_arguments={})],
        persona=[PersonaProbe(prompt="r", required_markers=["m"], forbidden_markers=[])],
        toolset_prompts=["t"],
        bench_prompts=["b"],
    )


def _record_ts(ts: datetime) -> datetime:
    return ts


def test_suite_version_stamped() -> None:
    assert _suite().suite_version == SUITE_VERSION == "v1"


def test_load_suite_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "suite_v1.json"
    path.write_text(json.dumps(_suite().model_dump(mode="json")), encoding="utf-8")
    loaded = load_suite(path)
    assert loaded.fidelity[0].action_type == "A"
    with pytest.raises(ValueError, match="version"):
        bad = tmp_path / "bad.json"
        payload = _suite().model_dump(mode="json")
        payload["suite_version"] = "v999"
        bad.write_text(json.dumps(payload), encoding="utf-8")
        load_suite(bad)


def test_temporal_split_enforced() -> None:
    suite = _suite(case_ts=datetime(2026, 8, 20, tzinfo=UTC))
    assert temporal_split_ok([datetime(2026, 8, 1, tzinfo=UTC)], suite)
    assert not temporal_split_ok([datetime(2026, 8, 16, tzinfo=UTC)], suite)
    contaminated = _suite(case_ts=datetime(2026, 8, 1, tzinfo=UTC))
    assert not temporal_split_ok([datetime(2026, 8, 1, tzinfo=UTC)], contaminated)


def test_persona_battery_has_fifty_probes() -> None:
    from xnch_train.evalharness.suites import default_persona_battery

    battery = default_persona_battery()
    assert len(battery) == 50
    assert all(p.required_markers or p.forbidden_markers for p in battery)
