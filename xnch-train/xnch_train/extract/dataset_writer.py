"""Atomic dataset persistence — the only sanctioned path to disk.

Enforces the ADR §1 hard requirement structurally: raw (unscrubbed) records
are refused, and loading a dataset without a valid manifest raises.
"""
from collections.abc import Sequence
import json
from pathlib import Path

from ..models.manifest import (
    MANIFEST_FILENAME,
    RECORDS_FILENAME,
    ScrubManifest,
    validate_dataset,
)
from ..models.records import ScrubStatus, TrainingRecord, read_jsonl, write_jsonl


def write_dataset(
    records: Sequence[TrainingRecord], manifest: ScrubManifest, out_dir: Path
) -> Path:
    dirty = [r.trace_id for r in records if r.scrub_status is not ScrubStatus.SCRUBBED]
    if dirty:
        raise ValueError(f"refusing raw (unscrubbed) records, e.g. {dirty[:3]}")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / RECORDS_FILENAME, list(records))
    tmp = out_dir / (MANIFEST_FILENAME + ".tmp")
    tmp.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")
    tmp.replace(out_dir / MANIFEST_FILENAME)
    return out_dir


def load_dataset(dataset_dir: Path) -> tuple[list[TrainingRecord], ScrubManifest]:
    validation = validate_dataset(dataset_dir)
    if not validation.valid:
        raise ValueError(f"invalid dataset {dataset_dir}: {validation.reasons}")
    manifest = ScrubManifest.model_validate(
        json.loads((dataset_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    )
    return read_jsonl(dataset_dir / RECORDS_FILENAME), manifest
