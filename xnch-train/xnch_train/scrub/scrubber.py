# xnch_train/scrub/scrubber.py
"""Scrub stage — runs before anything touches a dataset file (ADR §1).

Layers applied in order: secret-pattern denylist → entity pseudonymization.
Field blocklist is structural: TrainingRecord carries no raw-payload field,
so raw payloads can never be exported.
"""
import re
from collections.abc import Sequence

from ..models.records import ScrubStatus, TrainingRecord
from .patterns import CARD_CANDIDATE, find_secret_spans
from .pseudonymize import EntityPseudonymizer

_EMAIL: re.Pattern[str] = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
_DIGITS: re.Pattern[str] = re.compile(r"(?<!\d)\d{7,}(?!\d)")

_SCRUBBED_TEXT_FIELDS = ("input_context", "output")


def _merge_spans(spans: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Merge overlapping spans, retaining the earliest-starting rule per region."""
    merged: list[list[str | int]] = []
    for rule, start, end in sorted(spans, key=lambda s: (s[1], -s[2])):
        if merged and start < int(merged[-1][2]):
            merged[-1][2] = max(int(merged[-1][2]), end)
        else:
            merged.append([rule, start, end])
    return [(str(r), int(s), int(e)) for r, s, e in merged]


class Scrubber:
    """Last gate before datasets (ADR §1).

    Overlapping secret spans are merged — earliest-starting rule wins — and
    applied right-to-left so offsets stay valid. Card-shaped digit runs that
    failed the Luhn check survive every layer untouched.
    """

    def __init__(self, key: bytes) -> None:
        self._pseudo = EntityPseudonymizer(key)
        self._totals: dict[str, int] = {}

    def scrub(self, record: TrainingRecord) -> TrainingRecord:
        self._totals = {}
        data = record.model_dump()
        for field in _SCRUBBED_TEXT_FIELDS:
            data[field] = self._scrub_text(str(data[field]))
        data["scrub_status"] = ScrubStatus.SCRUBBED
        return TrainingRecord.model_validate(data)

    def scrub_many(
        self, records: Sequence[TrainingRecord]
    ) -> tuple[list[TrainingRecord], dict[str, int]]:
        totals: dict[str, int] = {}
        scrubbed: list[TrainingRecord] = []
        for record in records:
            new = self.scrub(record)
            scrubbed.append(new)
            for rule, n in self._totals.items():
                totals[rule] = totals.get(rule, 0) + n
        return scrubbed, totals

    def _scrub_text(self, text: str) -> str:
        merged = _merge_spans(find_secret_spans(text))
        for rule, start, end in sorted(merged, key=lambda s: s[2], reverse=True):
            text = text[:start] + f"[REDACTED:{rule}]" + text[end:]
            self._tally(rule)
        pieces: list[str] = []
        cursor = 0
        email_hits = 0
        digit_hits = 0
        for m in CARD_CANDIDATE.finditer(text):
            plain = text[cursor:m.start()]
            if plain:
                pieces.append(self._pseudo.pseudonymize(plain))
                email_hits += len(_EMAIL.findall(plain))
                digit_hits += len(_DIGITS.findall(plain))
            pieces.append(m.group(0))
            cursor = m.end()
        tail = text[cursor:]
        if tail:
            pieces.append(self._pseudo.pseudonymize(tail))
            email_hits += len(_EMAIL.findall(tail))
            digit_hits += len(_DIGITS.findall(tail))
        if email_hits:
            self._tally("email", email_hits)
        if digit_hits:
            self._tally("digit_run", digit_hits)
        return "".join(pieces)

    def _tally(self, rule: str, n: int = 1) -> None:
        self._totals[rule] = self._totals.get(rule, 0) + n
