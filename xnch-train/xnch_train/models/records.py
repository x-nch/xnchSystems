"""Canonical training record — the single shape every extractor must emit.

Canonical shape per ADR §1: {trace_id, ts, source, input_context, output,
outcome, verdict, scrub_status}. ``corrects_decision_id`` is an additive
Phase-2 linkage field (no upstream column exists yet — see ADR OQ2).
"""
import json
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field


class RecordSource(StrEnum):
    TRACE = "trace"
    VERDICT = "verdict"
    CORRECTION = "correction"
    OUTCOME = "outcome"


class VerdictKind(StrEnum):
    APPROVE = "APPROVE"
    BLOCK = "BLOCK"
    MODIFY = "MODIFY"


class OutcomeKind(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILURE = "FAILURE"


class ScrubStatus(StrEnum):
    RAW = "raw"
    SCRUBBED = "scrubbed"


class TrainingRecord(BaseModel):
    """One trainable observation, post-extraction (pre-scrub unless stated)."""

    trace_id: Annotated[str, Field(min_length=1)]
    ts: datetime
    source: RecordSource
    input_context: str = ""
    output: str = ""
    outcome: OutcomeKind | None = None
    verdict: VerdictKind | None = None
    corrects_decision_id: str = ""
    scrub_status: ScrubStatus = ScrubStatus.RAW


def write_jsonl(path: Path, records: Sequence[TrainingRecord]) -> int:
    """Atomically write records as JSON Lines; returns count written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    n = 0
    with tmp.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) + "\n")
            n += 1
    tmp.replace(path)
    return n


def read_jsonl(path: Path) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(TrainingRecord.model_validate(json.loads(line)))
    return records
