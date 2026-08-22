"""Scrub manifest — audit trail proving a dataset was scrubbed, by whom/what.

Hard requirement (ADR §1): a dataset without a manifest is invalid input to
any trainer or evaluator. When a sign-off secret is supplied to
``validate_dataset`` the operator_signoff hash is recomputed and compared,
so tampering with the manifest body invalidates the dataset; without a
secret only structural validity is checked.
"""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, Field

from ..scrub.patterns import PATTERN_SET_VERSION

MANIFEST_FILENAME = "scrub_manifest.json"
RECORDS_FILENAME = "records.jsonl"


class ScrubManifest(BaseModel):
    pattern_set_version: str
    rule_counts: Annotated[dict[str, int], Field(default_factory=dict)]
    operator_signoff: str
    created_at: datetime


class DatasetValidation(BaseModel):
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    record_count: int = 0


def _signing_payload(manifest: ScrubManifest) -> str:
    """Canonical pre-hash body shared by build and verify.

    Covers pattern_set_version + rule_counts (``created_at`` records when
    signing happened but is not attested).
    """
    body: dict[str, Any] = {
        "pattern_set_version": manifest.pattern_set_version,
        "rule_counts": manifest.rule_counts,
    }
    return json.dumps(body, sort_keys=True) + "|"


def build_scrub_manifest(rule_counts: dict[str, int], signoff_secret: str) -> ScrubManifest:
    """Sign-off hash covers the manifest body minus ``created_at`` plus the
    local secret — builds with identical inputs are byte-identical in
    signature; ``created_at`` records when signing happened but is not attested."""
    manifest = ScrubManifest(
        pattern_set_version=PATTERN_SET_VERSION,
        rule_counts=dict(rule_counts),
        operator_signoff="",
        created_at=datetime.now(tz=UTC),
    )
    payload = _signing_payload(manifest) + signoff_secret
    manifest.operator_signoff = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return manifest


def validate_dataset(
    dataset_dir: Path, signoff_secret: str | None = None
) -> DatasetValidation:
    reasons: list[str] = []
    records_path = dataset_dir / RECORDS_FILENAME
    manifest_path = dataset_dir / MANIFEST_FILENAME
    record_count = 0

    if not records_path.is_file():
        reasons.append(f"missing {RECORDS_FILENAME}")
    else:
        record_count = sum(
            1 for line in records_path.open(encoding="utf-8") if line.strip()
        )

    if not manifest_path.is_file():
        reasons.append(f"missing {MANIFEST_FILENAME}")
    else:
        try:
            manifest = ScrubManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 — any parse failure invalidates
            manifest = None
            reasons.append(f"unparseable manifest: {exc}")
        if manifest is not None:
            if manifest.pattern_set_version != PATTERN_SET_VERSION:
                reasons.append(
                    f"stale pattern_set_version {manifest.pattern_set_version!r}"
                    f" != current {PATTERN_SET_VERSION!r}"
                )
            if len(manifest.operator_signoff) != 64:
                reasons.append("operator_signoff missing or malformed")
            elif signoff_secret:
                expected = hashlib.sha256(
                    (_signing_payload(manifest) + signoff_secret).encode("utf-8")
                ).hexdigest()
                if manifest.operator_signoff != expected:
                    reasons.append("operator_signoff verification failed")

    return DatasetValidation(valid=not reasons, reasons=reasons, record_count=record_count)
