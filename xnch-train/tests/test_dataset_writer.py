"""Dataset writer enforces scrub-before-dataset and manifest presence."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from xnch_train.cli import app
from xnch_train.evalharness.suites import load_suite
from xnch_train.extract.dataset_writer import load_dataset, write_dataset
from xnch_train.models.manifest import build_scrub_manifest
from xnch_train.models.records import (
    RecordSource,
    ScrubStatus,
    TrainingRecord,
)


def _make_record(scrubbed: bool) -> TrainingRecord:
    return TrainingRecord(
        trace_id="tr-1",
        ts=datetime(2026, 8, 1, tzinfo=UTC),
        source=RecordSource.TRACE,
        input_context="ctx",
        output="out",
        scrub_status=ScrubStatus.SCRUBBED if scrubbed else ScrubStatus.RAW,
    )


def test_write_refuses_raw_records(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="raw"):
        write_dataset([_make_record(scrubbed=False)],
                      build_scrub_manifest({}, "s"), tmp_path / "ds")


def test_write_and_load_round_trip(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    manifest = build_scrub_manifest({"api_key": 1}, "s")
    written = write_dataset([_make_record(scrubbed=True)], manifest, ds)
    assert written == ds
    assert (ds / "records.jsonl").is_file()
    assert (ds / "scrub_manifest.json").is_file()
    records, loaded_manifest = load_dataset(ds)
    assert len(records) == 1
    assert loaded_manifest.pattern_set_version == manifest.pattern_set_version


def test_load_rejects_unmanifested_dataset(tmp_path: Path) -> None:
    ds = tmp_path / "ds"
    write_dataset([_make_record(scrubbed=True)], build_scrub_manifest({}, "s"), ds)
    (ds / "scrub_manifest.json").unlink()
    with pytest.raises(ValueError, match="invalid"):
        load_dataset(ds)


def test_cli_validate_reports_invalid(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["validate-dataset", str(tmp_path / "empty")])
    assert result.exit_code == 1
    assert "valid" in result.output.lower()


def test_load_dataset_forwards_signoff_secret(tmp_path: Path) -> None:
    ds = write_dataset([_make_record(scrubbed=True)],
                       build_scrub_manifest({"api_key": 1}, "sign-secret"), tmp_path / "ds")
    records, _manifest = load_dataset(ds, signoff_secret="sign-secret")
    assert len(records) == 1
    with pytest.raises(ValueError, match="verification failed"):
        load_dataset(ds, signoff_secret="wrong-secret")


def test_cli_suite_writes_starter(tmp_path: Path) -> None:
    runner = CliRunner()
    out_path = tmp_path / "suite_v1.json"
    result = runner.invoke(app, ["suite", "--out", str(out_path)])
    assert result.exit_code == 0
    loaded = load_suite(out_path)
    assert len(loaded.persona) == 50
