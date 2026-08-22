"""Canonical TrainingRecord shape, validation, and JSONL round-trip."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from xnch_train.models.records import (
    OutcomeKind,
    RecordSource,
    ScrubStatus,
    TrainingRecord,
    VerdictKind,
    read_jsonl,
    write_jsonl,
)


def _make_record(**overrides: object) -> TrainingRecord:
    base: dict[str, object] = {
        "trace_id": "tr-1",
        "ts": datetime(2026, 8, 1, tzinfo=UTC),
        "source": RecordSource.VERDICT,
        "input_context": '{"action": {}}',
        "output": '{"verdict": "BLOCK"}',
        "verdict": VerdictKind.BLOCK,
    }
    base.update(overrides)
    return TrainingRecord.model_validate(base)


def test_record_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        TrainingRecord.model_validate({"trace_id": "x"})


def test_record_defaults() -> None:
    r = _make_record(input_context="", output="")
    assert r.outcome is None
    assert r.verdict == VerdictKind.BLOCK
    assert r.scrub_status is ScrubStatus.RAW
    assert r.corrects_decision_id == ""


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    records = [
        _make_record(),
        _make_record(trace_id="tr-2", source=RecordSource.OUTCOME,
                     outcome=OutcomeKind.SUCCESS),
    ]
    n = write_jsonl(path, records)
    assert n == 2
    loaded = read_jsonl(path)
    assert loaded == records


def test_jsonl_is_line_delimited_json(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    write_jsonl(path, [_make_record()])
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["source"] == "verdict"
    assert payload["scrub_status"] == "raw"
