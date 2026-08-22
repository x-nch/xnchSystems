"""xnch-train — local-first, fully-gated training subsystem (Phase 0)."""
from .config import XtrainSettings
from .models.manifest import ScrubManifest, validate_dataset
from .models.records import TrainingRecord, read_jsonl, write_jsonl

__all__ = [
    "ScrubManifest",
    "TrainingRecord",
    "XtrainSettings",
    "read_jsonl",
    "validate_dataset",
    "write_jsonl",
]
