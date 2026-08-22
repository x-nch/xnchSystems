"""Eval suite container — version-stamped, temporally split (ADR §3).

Suites are immutable artifacts: bump SUITE_VERSION whenever contents change;
the incumbent must be re-scored whenever the version bumps.
"""
import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .metrics import ActionCase, PersonaProbe, RejectionCase

SUITE_VERSION = "v1"

_OPENERS: tuple[str, ...] = (
    "Summarize", "Explain", "Plan", "Check", "Deploy",
    "Report", "Compare", "List", "Draft", "Review",
)
_TOPICS: tuple[str, ...] = (
    "the deploy pipeline", "GPU capacity", "memory tiers",
    "the incident timeline", "quota usage", "backup status",
    "service health", "access requests", "pending goals", "latency trends",
)
_FILLERS: tuple[str, ...] = ("um", "uh", "kinda", "sorta")


def default_persona_battery() -> list[PersonaProbe]:
    """Fixed 50-prompt Nexi voice battery, generated deterministically.

    Voice contract encoded as marker rules: concise/no-filler, no emojis,
    no apology filler; every probe carries at least one marker rule.
    """
    probes: list[PersonaProbe] = []
    for i in range(50):
        opener = _OPENERS[i % len(_OPENERS)]
        topic = _TOPICS[(i // len(_OPENERS)) % len(_TOPICS)]
        required = ["concise"] if i % 2 == 0 else []
        forbidden = ["sorry"] if i % 3 == 0 else [_FILLERS[i % 2]]
        if not required and not forbidden:
            forbidden = ["sorry"]
        probes.append(PersonaProbe(
            prompt=f"{opener} {topic}. Be brief.",
            required_markers=required,
            forbidden_markers=forbidden,
        ))
    return probes


class EvalSuite(BaseModel):
    suite_version: str = SUITE_VERSION
    cutoff_ts: datetime
    fidelity: list[ActionCase] = Field(default_factory=list)
    rejection: list[RejectionCase] = Field(default_factory=list)
    persona: list[PersonaProbe] = Field(default_factory=list)
    toolset_prompts: list[str] = Field(default_factory=list)
    bench_prompts: list[str] = Field(default_factory=list)

    @property
    def case_source_tss(self) -> list[datetime]:
        tss = [c.source_ts for c in self.fidelity]
        tss += [c.source_ts for c in self.rejection]
        return tss


def load_suite(path: Path) -> EvalSuite:
    suite = EvalSuite.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if suite.suite_version != SUITE_VERSION:
        raise ValueError(
            f"suite version mismatch: file={suite.suite_version!r} harness={SUITE_VERSION!r}"
        )
    return suite


def temporal_split_ok(train_record_tss: list[datetime], suite: EvalSuite) -> bool:
    """Contamination guard: all training data strictly BEFORE the cutoff;
    all eval case provenance AT/AFTER the cutoff (ADR §3, mandatory)."""
    if any(ts >= suite.cutoff_ts for ts in train_record_tss):
        return False
    return all(ts >= suite.cutoff_ts for ts in suite.case_source_tss)
