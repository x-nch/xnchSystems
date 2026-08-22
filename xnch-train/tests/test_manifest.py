"""Scrub manifest build/sign-off and dataset validity gate."""
import json
from datetime import UTC, datetime
from pathlib import Path

from xnch_train.models.manifest import (
    ScrubManifest,
    build_scrub_manifest,
    validate_dataset,
)
from xnch_train.models.records import RecordSource, TrainingRecord, write_jsonl


def _make_record(trace_id: str = "tr-1") -> TrainingRecord:
    return TrainingRecord(
        trace_id=trace_id,
        ts=datetime(2026, 8, 1, tzinfo=UTC),
        source=RecordSource.TRACE,
    )


def _write_dataset(dir_: Path, *, manifest: bool = True, records: int = 2) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    write_jsonl(dir_ / "records.jsonl",
                [_make_record(f"tr-{i}") for i in range(records)])
    if manifest:
        m = build_scrub_manifest({"api_key": 3}, "sign-secret")
        (dir_ / "scrub_manifest.json").write_text(
            json.dumps(m.model_dump(mode="json")), encoding="utf-8")


def test_signoff_hash_covers_body_and_secret() -> None:
    m1 = build_scrub_manifest({"api_key": 3}, "s1")
    m2 = build_scrub_manifest({"api_key": 3}, "s1")
    m3 = build_scrub_manifest({"api_key": 3}, "s2")
    assert m1.operator_signoff == m2.operator_signoff
    assert m1.operator_signoff != m3.operator_signoff


def test_valid_dataset_passes(tmp_path: Path) -> None:
    _write_dataset(tmp_path / "ds")
    result = validate_dataset(tmp_path / "ds")
    assert result.valid
    assert result.reasons == []
    assert result.record_count == 2


def test_missing_manifest_invalidates(tmp_path: Path) -> None:
    _write_dataset(tmp_path / "ds", manifest=False)
    result = validate_dataset(tmp_path / "ds")
    assert not result.valid
    assert any("manifest" in r for r in result.reasons)


def test_missing_records_file_invalidates(tmp_path: Path) -> None:
    (tmp_path / "ds").mkdir()
    result = validate_dataset(tmp_path / "ds")
    assert not result.valid
    assert any("records.jsonl" in r for r in result.reasons)


def test_wrong_pattern_set_version_invalidates(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    _write_dataset(ds)
    stale = ScrubManifest(
        pattern_set_version="1999-01.1",
        rule_counts={"api_key": 0},
        operator_signoff="deadbeef",
        created_at=datetime.now(tz=UTC),
    )
    (ds / "scrub_manifest.json").write_text(
        json.dumps(stale.model_dump(mode="json")), encoding="utf-8")
    result = validate_dataset(ds)
    assert not result.valid
    assert any("pattern_set_version" in r for r in result.reasons)
