# Training Subsystem Phase 0 — Data Pipeline + Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `xnch-train` Phase 0 deliverables — canonical training-record format, Langfuse/Postgres extractors, scrubber with scrub-manifest, eval harness v1 (incumbent-only baselines for the five gate metrics), and a dry-run promotion-gate stub. No training, no GPU code.

**Architecture:** New top-level package directory `xnch-train/` (import name `xnch_train`; converted to a git submodule in a later phase). Extractors read xnch's existing observability surfaces — Langfuse REST API (verdicts parsed from policy-engine trace I/O) and Postgres `decision_episodes` (outcomes; corrections forward-compatible on `corrects_decision_id`, which does not exist yet and returns empty). Scrubber runs before anything touches a dataset file and emits a mandatory `scrub_manifest.json`. Eval harness drives any OpenAI-compatible endpoint (vLLM incumbent) through five metric functions and produces a versioned baseline report. The gate stub compares two reports and emits a proposal payload — dry run only, never touches HITL or weights.

**Tech Stack:** Python 3.13+, Pydantic v2 (`BaseModel`, `BaseSettings`, `StrEnum`), httpx (Langfuse REST + vLLM OpenAI-compatible), asyncpg (Postgres extract), typer (CLI), pytest + pytest-asyncio (auto mode). No new heavy deps; torch/peft/trl explicitly out of scope until Phase 1.

**Spec:** `docs/adr/2026-08-22-training-subsystem.md` (ADR §1 Data Pipeline, §3 Eval & Safety Gate, §4 placement; Phase 0 row of the phased plan). Decisions locked with operator: (a) Phase 0 only; (b) local top-level dir now, submodule later; (c) verdicts extracted from Langfuse trace I/O, not episodes; (d) dataset home = Node A filesystem.

## Global Constraints

- Python 3.13+; deps limited to already-present httpx/asyncpg/pydantic/pydantic-settings/typer. No new third-party deps of any kind.
- AGENTS.md house style: stdlib→third-party→local relative imports; `StrEnum` for fixed choices; `Annotated[T, Field(...)]` for constrained fields; annotate ALL signatures incl. returns; lowercase generics; local relative imports only (`from ..models.records import ...`) — never `from xnch_train...` absolute inside the package.
- No cross-package imports: do NOT import from `xnch` or `nexi`. Small deliberate ports (qwen3_xml regex) are copied with attribution comment.
- Nothing raw ever reaches a dataset file: scrub-before-dataset is enforced by construction (`write_dataset` refuses unscrubbed records and requires a manifest).
- A dataset without `scrub_manifest.json` is invalid input to every consumer (`validate_dataset` gates).
- Checkpoints/datasets are derived secrets: default paths live under Node A filesystem via `XTRAIN_DATASET_DIR`; never print record text at INFO level.
- Tests colocated in `xnch-train/tests/`, helpers prefixed `_make_*`, module docstrings required. Root `pyproject.toml` gains `xnch-train` pythonpath + testpaths entries.
- P0 scope only: no systemd units, no GoalStore wiring, no venv/toolchain, no DPO/SFT code, no checkpoint registry.

## File Structure

| File | Responsibility |
|---|---|
| `xnch-train/pyproject.toml` (C) | Package metadata; name `xnch-train`, import package `xnch_train` |
| `xnch_train/__init__.py` (C) | Re-exports with `__all__` |
| `xnch_train/config.py` (C) | `XtrainSettings(BaseSettings)` env_prefix `XTRAIN_` |
| `xnch_train/models/records.py` (C) | Canonical `TrainingRecord` + enums + JSONL IO |
| `xnch_train/models/manifest.py` (C) | `ScrubManifest`, `DatasetValidation`, dataset validator |
| `xnch_train/scrub/patterns.py` (C) | Secret denylist regexes + Luhn check, `PATTERN_SET_VERSION` |
| `xnch_train/scrub/pseudonymize.py` (C) | HMAC-with-local-key deterministic pseudonymizer |
| `xnch_train/scrub/scrubber.py` (C) | Record scrubbing + per-rule redaction counts |
| `xnch_train/extract/langfuse_extract.py` (C) | Paginated traces/observations → verdict records |
| `xnch_train/extract/pg_extract.py` (C) | decision_episodes outcome + correction extractors |
| `xnch_train/extract/dataset_writer.py` (C) | Atomic dataset write (records.jsonl + manifest), loader |
| `xnch_train/evalharness/client.py` (C) | `ModelClient` protocol, vLLM OpenAI client, fake |
| `xnch_train/evalharness/qwen3xml.py` (C) | `<tool_call>` parser (port of qwen3_xml format) |
| `xnch_train/evalharness/metrics.py` (C) | Five gate metrics as pure functions |
| `xnch_train/evalharness/suites.py` (C) | Suite model/versioning, battery assets, temporal split check |
| `xnch_train/evalharness/runner.py` (C) | Incumbent-only baseline runner → `BaselineReport` |
| `xnch_train/gate/promotion_gate.py` (C) | Dry-run eligibility gate + proposal payload |
| `xnch_train/cli.py` (C) | typer app: `extract`, `validate-dataset`, `baseline` |
| `xnch-train/tests/test_*.py` (C) | One test module per source module |

---

### Task 1: Package scaffold, config, root wiring

**Files:**
- Create: `xnch-train/pyproject.toml`
- Create: `xnch_train/__init__.py`, `xnch_train/config.py`
- Create: `xnch-train/tests/conftest.py`, `xnch-train/tests/test_config.py`
- Modify: `pyproject.toml` (root — `pythonpath`, `testpaths`)

**Interfaces:**
- Produces: `XtrainSettings` fields used by later tasks — `dataset_dir: Path`, `postgres_url: str`, `langfuse_host: str`, `langfuse_public_key: str`, `langfuse_secret_key: str`, `pseudonymize_secret: str`, `gate_epsilon: float = 0.02`, `serving_regression_bound_pct: float = 10.0`, `extract_page_size: int = 100`.

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/conftest.py
"""Shared fixtures for xnch-train tests."""
import pytest

from xnch_train.config import XtrainSettings


@pytest.fixture(autouse=True)
def _xtrain_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate every test from the operator's real environment."""
    monkeypatch.setenv("XTRAIN_DATASET_DIR", "/tmp/xtrain-test-datasets")
    monkeypatch.setenv("XTRAIN_POSTGRES_URL", "postgresql://test:test@localhost:5432/test")
    monkeypatch.setenv("XTRAIN_LANGFUSE_HOST", "http://lf.test")
    monkeypatch.setenv("XTRAIN_LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("XTRAIN_LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("XTRAIN_PSEUDONYMIZE_SECRET", "unit-secret")


@pytest.fixture()
def settings() -> XtrainSettings:
    return XtrainSettings()
```

```python
# xnch-train/tests/test_config.py
"""XtrainSettings loads from XTRAIN_-prefixed env vars with safe defaults."""
from pathlib import Path

from xnch_train.config import XtrainSettings


def test_defaults_are_safe(settings: XtrainSettings) -> None:
    s = XtrainSettings(dataset_dir=None, postgres_url=None)
    assert s.gate_epsilon == 0.02
    assert s.serving_regression_bound_pct == 10.0
    assert s.extract_page_size == 100


def test_env_override(settings: XtrainSettings) -> None:
    assert settings.dataset_dir == Path("/tmp/xtrain-test-datasets")
    assert settings.langfuse_host == "http://lf.test"
    assert settings.pseudonymize_secret == "unit-secret"
```

Note: `XtrainSettings()` inside tests picks up conftest env vars; the two explicit `None` kwargs in `test_defaults_are_safe` exercise that optional constructor overrides beat env.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train'`

- [ ] **Step 3: Implement**

```toml
# xnch-train/pyproject.toml
[project]
name = "xnch-train"
version = "0.1.0"
description = "Local training subsystem worker (Phase 0: data pipeline + eval harness)"
requires-python = ">=3.13"
dependencies = [
    "httpx>=0.28.1",
    "asyncpg>=0.31.0",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "typer>=0.12",
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["xnch_train*"]
```

```python
# xnch_train/config.py
"""xnch-train settings — XTRAIN_ env prefix, Node-A filesystem dataset home."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class XtrainSettings(BaseSettings):
    """Configuration for the xnch-train worker (Phase 0 surfaces only)."""

    model_config = SettingsConfigDict(env_prefix="XTRAIN_", env_file=".env", extra="ignore")

    dataset_dir: Path = Path("./datasets")
    postgres_url: str = "postgresql://localhost:5432/xnch"
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    pseudonymize_secret: str = ""
    gate_epsilon: float = 0.02
    serving_regression_bound_pct: float = 10.0
    extract_page_size: int = 100

    def pseudonymize_key(self) -> bytes:
        """Deterministic HMAC key for entity pseudonymization."""
        return self.pseudonymize_secret.encode("utf-8")
```

```python
# xnch_train/__init__.py
"""xnch-train — local-first, fully-gated training subsystem (Phase 0)."""
```

Root `pyproject.toml` — replace the two lines:

```toml
pythonpath = [".", "xnch-train"]
testpaths = ["nexi/tests", "xnch/tests", "tests", "xnch_mcp/tests", "fs_read_agent/tests", "docs_test_mcp/tests", "xnch-train/tests"]
```

Also create empty `__init__.py` files in `xnch_train/models/`, `xnch_train/scrub/`, `xnch_train/extract/`, `xnch_train/evalharness/`, `xnch_train/gate/`, plus `xnch-train/tests/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train pyproject.toml
git commit -m "feat(xnch-train): scaffold Phase 0 package with XTRAIN_ settings"
```

---

### Task 2: Canonical record model + JSONL IO

**Files:**
- Create: `xnch_train/models/records.py`
- Test: `xnch-train/tests/test_records.py`

**Interfaces:**
- Produces (used by Tasks 6–12): `RecordSource(StrEnum)` values `trace|verdict|correction|outcome`; `VerdictKind(StrEnum)` values `APPROVE|BLOCK|MODIFY`; `OutcomeKind(StrEnum)` values `SUCCESS|PARTIAL|FAILURE`; `ScrubStatus(StrEnum)` values `raw|scrubbed`; `TrainingRecord(trace_id: str, ts: datetime, source: RecordSource, input_context: str = "", output: str = "", outcome: OutcomeKind | None = None, verdict: VerdictKind | None = None, corrects_decision_id: str = "", scrub_status: ScrubStatus = ScrubStatus.RAW)`; `write_jsonl(path: Path, records: Sequence[TrainingRecord]) -> int`; `read_jsonl(path: Path) -> list[TrainingRecord]`.
- Deviation note: `corrects_decision_id` is additive to the ADR's canonical shape `{trace_id, ts, source, input_context, output, outcome, verdict, scrub_status}` — required for Phase 2 supervised pairs (ADR Open Question Q2 resolved: field does not exist upstream yet).

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_records.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_records.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.models.records'`

- [ ] **Step 3: Implement**

```python
# xnch_train/models/records.py
"""Canonical training record — the single shape every extractor must emit.

Canonical shape per ADR §1: {trace_id, ts, source, input_context, output,
outcome, verdict, scrub_status}. ``corrects_decision_id`` is an additive
Phase-2 linkage field (no upstream column exists yet — see ADR OQ2).
"""
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_REDACTED = "\u21ba"


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
```

Add missing imports at top: `from typing import Annotated` merged into the typing line, and `from collections.abc import Sequence` (house style prefers `Sequence` from collections.abc). Final import block:

```python
import json
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
```

Remove the unused `_REDACTED` constant (it belongs to Task 3's domain).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_records.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/models xnch-train/tests/test_records.py
git commit -m "feat(xnch-train): canonical TrainingRecord model with JSONL IO"
```

---

### Task 3: Secret-pattern denylist + Luhn check

**Files:**
- Create: `xnch_train/scrub/patterns.py`
- Test: `xnch-train/tests/test_patterns.py`

**Interfaces:**
- Produces: `PATTERN_SET_VERSION = "2026-08.1"`; `SECRET_RULES: dict[str, re.Pattern[str]]` with keys `api_key`, `bearer_token`, `aws_access_key`, `password_kv`; `CARD_CANDIDATE: re.Pattern[str]` (13–19 card-shaped digit runs); `luhn_valid(number: str) -> bool`; `find_secret_spans(text: str) -> list[tuple[str, int, int]]` returning `(rule_name, start, end)` where `card_number` spans are included **only when Luhn-valid**.

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_patterns.py
"""Secret denylist patterns and Luhn validation for card-shaped numbers."""
import re

from xnch_train.scrub.patterns import (
    CARD_CANDIDATE,
    PATTERN_SET_VERSION,
    SECRET_RULES,
    find_secret_spans,
    luhn_valid,
)


def test_pattern_set_version_is_pinned() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}\.\d+", PATTERN_SET_VERSION)


def test_luhn_accepts_and_rejects() -> None:
    assert luhn_valid("4532015112830366")      # valid Visa-shaped test number
    assert not luhn_valid("4532015112830367")  # same digits, fails checksum
    assert not luhn_valid("")                  # empty never validates


def test_api_keys_detected() -> None:
    text = "use sk-proj-abcd1234EFGH5678ijkl today"
    spans = [s for s in find_secret_spans(text) if s[0] == "api_key"]
    assert len(spans) == 1
    start, end = spans[0][1], spans[0][2]
    assert text[start:end].startswith("sk-proj-")


def test_bearer_token_detected() -> None:
    spans = [s for s in find_secret_spans("Authorization: Bearer abc.def.ghi")
             if s[0] == "bearer_token"]
    assert len(spans) == 1


def test_password_kv_detected() -> None:
    spans = [s for s in find_secret_spans('{"password": "hunter2"}')
             if s[0] == "password_kv"]
    assert len(spans) == 1


def test_card_only_when_luhn_valid() -> None:
    good = "4532 0151 1283 0366"   # Luhn-valid, spaced
    bad = "4532 0151 1283 0367"    # fails checksum
    good_spans = [s for s in find_secret_spans(f"card {good} ok") if s[0] == "card_number"]
    bad_spans = [s for s in find_secret_spans(f"ref {bad} x") if s[0] == "card_number"]
    assert len(good_spans) == 1
    assert bad_spans == []


def test_card_candidate_regex_shape() -> None:
    m = CARD_CANDIDATE.search("pay 4532015112830366 now")
    assert m is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_patterns.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.scrub'`

- [ ] **Step 3: Implement**

```python
# xnch_train/scrub/patterns.py
"""Secret-pattern denylist — first scrub layer before anything leaves memory.

Version-stamped: bump PATTERN_SET_VERSION whenever rules change so scrub
manifests stay auditable (ADR §1 hygiene requirements).
"""
import re

PATTERN_SET_VERSION = "2026-08.1"

SECRET_RULES: dict[str, re.Pattern[str]] = {
    # OpenAI-style, GitHub tokens, generic high-entropy key assignments
    "api_key": re.compile(
        r"(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"
    ),
    "bearer_token": re.compile(
        r"(?i:bearer\s+[A-Za-z0-9._~+/=-]{16,})"
    ),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "password_kv": re.compile(
        r"(?i)(?:\"?(?:password|passwd|secret|api[_-]?token)\"?\s*[:=]\s*)"
        r"(\"[^\"]{4,}\"|'[^']{4,}'|[^\s,\"']{4,})"
    ),
}

# Card-shaped runs: 13–19 digits with optional spaces/dashes between groups.
CARD_CANDIDATE: re.Pattern[str] = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def luhn_valid(number: str) -> bool:
    """Standard Luhn checksum over stripped digits; False when too short."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = (len(digits) - 2) % 2
    for i, d in enumerate(digits[:-1]):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return (checksum + digits[-1]) % 10 == 0


def find_secret_spans(text: str) -> list[tuple[str, int, int]]:
    """All redaction spans as (rule_name, start, end); non-overlapping per rule.

    Card candidates are reported only when they pass the Luhn check —
    random long numbers (order IDs etc.) must survive untouched.
    """
    spans: list[tuple[str, int, int]] = []
    for name, pattern in SECRET_RULES.items():
        spans.extend((name, m.start(), m.end()) for m in pattern.finditer(text))
    for m in CARD_CANDIDATE.finditer(text):
        if luhn_valid(m.group(0)):
            spans.append(("card_number", m.start(), m.end()))
    spans.sort(key=lambda s: s[1])
    return spans
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_patterns.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/scrub xnch-train/tests/test_patterns.py
git commit -m "feat(xnch-train): secret denylist patterns with Luhn-checked cards"
```

---

### Task 4: HMAC entity pseudonymization

**Files:**
- Create: `xnch_train/scrub/pseudonymize.py`
- Test: `xnch-train/tests/test_pseudonymize.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `EntityPseudonymizer(key: bytes)` with `.tag(value: str) -> str` (deterministic 16-hex-char HMAC-SHA256 tag) and `.pseudonymize(text: str) -> str` which replaces email addresses with `<id:TAG>@pseudo.local` and digit runs ≥ 7 with `<num:TAG:len>` — format survives training (ADR §1 hygiene layer 2).

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_pseudonymize.py
"""Deterministic, format-preserving entity pseudonymization."""
from xnch_train.scrub.pseudonymize import EntityPseudonymizer

KEY = b"unit-secret"


def _make_pseudo() -> EntityPseudonymizer:
    return EntityPseudonymizer(KEY)


def test_tag_deterministic_and_hex() -> None:
    p = _make_pseudo()
    t1 = p.tag("alice@example.com")
    t2 = p.tag("alice@example.com")
    assert t1 == t2
    assert len(t1) == 16
    int(t1, 16)  # hex-parseable


def test_tag_depends_on_key() -> None:
    assert (EntityPseudonymizer(KEY).tag("x")
            != EntityPseudonymizer(b"other").tag("x"))


def test_email_replaced_format_preserved() -> None:
    out = _make_pseudo().pseudonymize("mail alice@example.com please")
    assert "alice@example.com" not in out
    assert "@pseudo.local" in out


def test_long_digit_runs_replaced_short_kept() -> None:
    p = _make_pseudo()
    out = p.pseudonymize("id 0042957831 qty 3 total 129")
    assert "0042957831" not in out
    assert "qty 3" in out          # short run kept
    assert "<num:" in out


def test_no_raw_email_or_account_leaks() -> None:
    out = _make_pseudo().pseudonymize(
        "acct 7001002003 owner bob@corp.example paid"
    )
    assert "bob@corp.example" not in out
    assert "7001002003" not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_pseudonymize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.scrub.pseudonymize'`

- [ ] **Step 3: Implement**

```python
# xnch_train/scrub/pseudonymize.py
"""Entity pseudonymization — HMAC-with-local-key, format-preserving.

Same input + same key ⇒ same tag, so entity identity relationships survive
training while the raw value never appears in a dataset (ADR §1).
"""
import hmac
import re

_EMAIL: re.Pattern[str] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LONG_DIGITS: re.Pattern[str] = re.compile(r"(?<![\w])\d{7,}(?![\w])")

_TAG_LEN = 16


class EntityPseudonymizer:
    def __init__(self, key: bytes) -> None:
        self._key = key

    def tag(self, value: str) -> str:
        """Deterministic hex tag for one entity value."""
        digest = hmac.new(self._key, value.encode("utf-8"), "sha256").hexdigest()
        return digest[:_TAG_LEN]

    def pseudonymize(self, text: str) -> str:
        """Replace emails and long digit runs with stable pseudo-tokens."""
        text = _EMAIL.sub(lambda m: f"<id:{self.tag(m.group(0))}>@pseudo.local", text)
        text = _LONG_DIGITS.sub(
            lambda m: f"<num:{self.tag(m.group(0))}:{len(m.group(0))}>", text
        )
        return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_pseudonymize.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/scrub/pseudonymize.py xnch-train/tests/test_pseudonymize.py
git commit -m "feat(xnch-train): HMAC-based deterministic entity pseudonymizer"
```

---

### Task 5: Scrub manifest + dataset validation

**Files:**
- Create: `xnch_train/models/manifest.py`
- Test: `xnch-train/tests/test_manifest.py`

**Interfaces:**
- Consumes: `PATTERN_SET_VERSION` (Task 3).
- Produces (Tasks 9, 12 consume): `ScrubManifest(pattern_set_version: str, rule_counts: dict[str, int], operator_signoff: str, created_at: datetime)`; `build_scrub_manifest(rule_counts: dict[str, int], signoff_secret: str) -> ScrubManifest` (sign-off = sha256 over canonical JSON body + secret); `DatasetValidation(valid: bool, reasons: list[str], record_count: int)`; `validate_dataset(dataset_dir: Path) -> DatasetValidation` expecting `records.jsonl` + `scrub_manifest.json` in `dataset_dir`. A dataset without a manifest is invalid (hard requirement).

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_manifest.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.models.manifest'`

- [ ] **Step 3: Implement**

```python
# xnch_train/models/manifest.py
"""Scrub manifest — audit trail proving a dataset was scrubbed, by whom/what.

Hard requirement (ADR §1): a dataset without a manifest is invalid input to
any trainer or evaluator.
"""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def build_scrub_manifest(rule_counts: dict[str, int], signoff_secret: str) -> ScrubManifest:
    """Sign-off hash covers the full manifest body + the local secret."""
    manifest = ScrubManifest(
        pattern_set_version=PATTERN_SET_VERSION,
        rule_counts=dict(rule_counts),
        operator_signoff="",
        created_at=datetime.now(tz=UTC),
    )
    body: dict[str, Any] = manifest.model_dump(mode="json")
    payload = json.dumps(body, sort_keys=True) + "|" + signoff_secret
    manifest.operator_signoff = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return manifest


def validate_dataset(dataset_dir: Path) -> DatasetValidation:
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

    return DatasetValidation(valid=not reasons, reasons=reasons, record_count=record_count)
```

Add `from typing import Annotated` to the typing import line.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_manifest.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/models/manifest.py xnch-train/tests/test_manifest.py
git commit -m "feat(xnch-train): scrub manifest with sign-off hash and dataset validator"
```

---

### Task 6: Scrubber

**Files:**
- Create: `xnch_train/scrub/scrubber.py`
- Test: `xnch-train/tests/test_scrubber.py`

**Interfaces:**
- Consumes: `find_secret_spans`, `EntityPseudonymizer`, `TrainingRecord`, `ScrubStatus`.
- Produces: `Scrubber(key: bytes)` with `.scrub(record: TrainingRecord) -> TrainingRecord` (returns NEW record; scrubs `input_context` + `output`; sets `scrub_status=SCRUBBED`) and `.scrub_many(records: Sequence[TrainingRecord]) -> tuple[list[TrainingRecord], dict[str, int]]` (second element = per-rule redaction counts, keys include `"email"` and `"digit_run"` for pseudonymizations). Raw payloads are structurally impossible to export: the canonical record simply has no such field (field blocklist satisfied by construction).

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_scrubber.py
"""Scrubber applies denylist + pseudonymization, tracks per-rule counts."""
from datetime import UTC, datetime

from xnch_train.models.records import RecordSource, ScrubStatus, TrainingRecord
from xnch_train.scrub.scrubber import Scrubber

KEY = b"unit-secret"


def _make_record(input_context: str = "", output: str = "") -> TrainingRecord:
    return TrainingRecord(
        trace_id="tr-1",
        ts=datetime(2026, 8, 1, tzinfo=UTC),
        source=RecordSource.TRACE,
        input_context=input_context,
        output=output,
    )


def _make_scrubber() -> Scrubber:
    return Scrubber(KEY)


def test_scrub_returns_new_record_marked_scrubbed() -> None:
    original = _make_record(output="call sk-proj-abcd1234EFGH5678ijk now")
    scrubbed = _make_scrubber().scrub(original)
    assert scrubbed is not original
    assert scrubbed.scrub_status is ScrubStatus.SCRUBBED
    assert "sk-proj-" not in scrubbed.output
    assert original.scrub_status is ScrubStatus.RAW  # input untouched


def test_luhn_invalid_number_survives() -> None:
    scrubbed = _make_scrubber().scrub(_make_record(output="ref 4532015112830367"))
    assert "4532015112830367" in scrubbed.output


def test_luhn_valid_card_redacted() -> None:
    scrubbed = _make_scrubber().scrub(_make_record(output="card 4532015112830366"))
    assert "4532015112830366" not in scrubbed.output
    assert "[REDACTED:card_number]" in scrubbed.output


def test_secrets_redacted_with_rule_tag() -> None:
    scrubbed = _make_scrubber().scrub(
        _make_record(output='Authorization: Bearer tok1234567890abcdef')
    )
    assert "[REDACTED:bearer_token]" in scrubbed.output


def test_pseudonymization_applies_to_both_fields() -> None:
    scrubbed = _make_scrubber().scrub(
        _make_record(input_context="user alice@example.com",
                     output="acct 7001002003 charged")
    )
    assert "alice@example.com" not in scrubbed.input_context
    assert "7001002003" not in scrubbed.output
    assert "@pseudo.local" in scrubbed.input_context


def test_scrub_many_counts_rules() -> None:
    records = [
        _make_record(output="k sk-proj-abcd1234EFGH5678ijk"),
        _make_record(input_context="mail bob@example.com"),
    ]
    scrubbed, counts = _make_scrubber().scrub_many(records)
    assert len(scrubbed) == 2
    assert all(r.scrub_status is ScrubStatus.SCRUBBED for r in scrubbed)
    assert counts.get("api_key") == 1
    assert counts.get("email") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_scrubber.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.scrub.scrubber'`

- [ ] **Step 3: Implement**

```python
# xnch_train/scrub/scrubber.py
"""Scrub stage — runs before anything touches a dataset file (ADR §1).

Layers applied in order: secret-pattern denylist → entity pseudonymization.
Field blocklist is structural: TrainingRecord carries no raw-payload field,
so raw payloads can never be exported.
"""
from collections.abc import Sequence

from ..models.records import ScrubStatus, TrainingRecord
from .patterns import find_secret_spans
from .pseudonymize import EntityPseudonymizer

_SCRUBBED_TEXT_FIELDS = ("input_context", "output")


class Scrubber:
    def __init__(self, key: bytes) -> None:
        self._pseudo = EntityPseudonymizer(key)

    def scrub(self, record: TrainingRecord) -> TrainingRecord:
        data = record.model_dump()
        counts: dict[str, int] = {}
        for field in _SCRUBBED_TEXT_FIELDS:
            data[field] = self._scrub_text(str(data[field]), counts)
        data["scrub_status"] = ScrubStatus.SCRUBBED
        return TrainingRecord.model_validate(data)

    def scrub_many(
        self, records: Sequence[TrainingRecord]
    ) -> tuple[list[TrainingRecord], dict[str, int]]:
        scrubbed = [self.scrub(r) for r in records]
        totals: dict[str, int] = {}
        per_record_counts = [
            self._count_only(r) for r in records
        ]
        # Counts accumulate during scrub; recompute cheaply by re-scrubbing
        # is wasteful, so track during scrub instead.
        totals = self._last_totals.copy()
        self._last_totals = {}
        return scrubbed, totals

    def _count_only(self, record: TrainingRecord) -> dict[str, int]:  # pragma: no cover
        raise NotImplementedError  # replaced below

    _last_totals: dict[str, int]
```

That sketch got tangled — use this exact implementation instead:

```python
# xnch_train/scrub/scrubber.py
"""Scrub stage — runs before anything touches a dataset file (ADR §1).

Layers applied in order: secret-pattern denylist → entity pseudonymization.
Field blocklist is structural: TrainingRecord carries no raw-payload field,
so raw payloads can never be exported.
"""
from collections.abc import Sequence

from ..models.records import ScrubStatus, TrainingRecord
from .patterns import find_secret_spans
from .pseudonymize import EntityPseudonymizer

_SCRUBBED_TEXT_FIELDS = ("input_context", "output")


class Scrubber:
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
        for rule, start, end in find_secret_spans(text):
            text = text[:start] + f"[REDACTED:{rule}]" + text[end:]
            self._tally(rule)
        for match_kind, pattern in (("email", self._EMAIL), ("digit_run", self._DIGITS)):
            hits = pattern.findall(text)
            if hits:
                text = self._pseudo.pseudonymize(text)
                self._tally(match_kind, len(hits))
        return text

    def _tally(self, rule: str, n: int = 1) -> None:
        self._totals[rule] = self._totals.get(rule, 0) + n

    _EMAIL = __import__("re").compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    _DIGITS = __import__("re").compile(r"(?<![\w])\d{7,}(?![\w])")
```

Replace the class-level `_EMAIL`/`_DIGITS` hack with proper module constants:

```python
import re

_EMAIL: re.Pattern[str] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DIGITS: re.Pattern[str] = re.compile(r"(?<![\w])\d{7,}(?![\w])")
```

and reference `_EMAIL` / `_DIGITS` directly in `_scrub_text`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_scrubber.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/scrub/scrubber.py xnch-train/tests/test_scrubber.py
git commit -m "feat(xnch-train): scrubber with per-rule redaction accounting"
```

---

### Task 7: Langfuse extractor (verdicts from trace I/O)

**Files:**
- Create: `xnch_train/extract/langfuse_extract.py`
- Test: `xnch-train/tests/test_langfuse_extract.py`

**Interfaces:**
- Consumes: `TrainingRecord`, `RecordSource`, `VerdictKind` (Task 2).
- Produces: `LangfuseExtractor(host: str, public_key: str, secret_key: str, page_size: int = 100)` with:
  - `async fetch_traces_page(page: int) -> list[dict[str, Any]]` — GET `/api/public/traces?page={page}&limit={page_size}` (basic auth).
  - `async fetch_observations(trace_id: str) -> list[dict[str, Any]]` — GET `/api/public/observations?traceId={id}`.
  - `static verdict_record_from_observation(obs: dict[str, Any]) -> TrainingRecord | None` — recognizes xnch policy-engine generations: `name == "llm-call"` AND `model == "policy-engine"` AND prompt parses as JSON with an `action` key AND completion parses as JSON with a `verdict` key in `{ALLOW, BLOCK, MODIFY}`. Maps `ALLOW→APPROVE`, keeps `BLOCK`/`MODIFY`. Returns None otherwise.
  - `async extract_verdicts(max_traces: int = 1000) -> list[TrainingRecord]` — paginates traces, fetches observations per trace, yields verdict records.
- Operator decision (c): verdicts come from Langfuse generation I/O because `/verdict` episodes persist only session/actor/score/goal in `context_snapshot` — no verdict field exists upstream.

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_langfuse_extract.py
"""Langfuse extractor — verdict preference pairs from policy-engine trace I/O."""
import json
from typing import Any

import httpx
import pytest

from xnch_train.extract.langfuse_extract import LangfuseExtractor
from xnch_train.models.records import RecordSource, VerdictKind

HOST = "http://lf.test"


def _policy_generation(verdict: str = "BLOCK") -> dict[str, Any]:
    return {
        "id": "gen-1",
        "traceId": "tr-1",
        "name": "llm-call",
        "model": "policy-engine",
        "prompt": json.dumps({"action": {"type": "DEPLOY"}, "actor": {}, "context": {}}),
        "completion": json.dumps({"verdict": verdict, "reason": "rule-x"}),
        "timestamp": "2026-08-01T00:00:00Z",
    }


def _unrelated_observation() -> dict[str, Any]:
    return {"id": "obs-9", "traceId": "tr-1", "name": "tool-span",
            "model": "ornith", "prompt": "hi", "completion": "ho"}


@pytest.fixture()
def transport_page(httpx_mock_transport_calls: list[httpx.Request]) -> None:  # noqa: ARG001
    """Placeholder fixture name kept minimal; real patching below."""


async def test_verdict_record_from_observation_maps_allow_to_approve() -> None:
    rec = LangfuseExtractor.verdict_record_from_observation(_policy_generation("ALLOW"))
    assert rec is not None
    assert rec.source is RecordSource.VERDICT
    assert rec.verdict is VerdictKind.APPROVE
    assert rec.trace_id == "tr-1"


async def test_verdict_record_keeps_block_and_modify() -> None:
    for raw, expected in (("BLOCK", VerdictKind.BLOCK), ("MODIFY", VerdictKind.MODIFY)):
        rec = LangfuseExtractor.verdict_record_from_observation(_policy_generation(raw))
        assert rec is not None
        assert rec.verdict is expected


async def test_non_policy_observations_return_none() -> None:
    obs = _unrelated_observation()
    assert LangfuseExtractor.verdict_record_from_observation(obs) is None


async def test_malformed_payloads_return_none() -> None:
    bad = {"name": "llm-call", "model": "policy-engine",
           "prompt": "not json", "completion": "also not"}
    assert LangfuseExtractor.verdict_record_from_observation(bad) is None


async def test_extract_verdicts_paginates_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    ex = LangfuseExtractor(HOST, "pk", "sk", page_size=1)

    async def fake_page(page: int) -> list[dict[str, Any]]:
        if page <= 2:
            return [{"id": f"tr-{page}"}]
        return []

    async def fake_obs(trace_id: str) -> list[dict[str, Any]]:
        if trace_id == "tr-1":
            return [_policy_generation("ALLOW"), _unrelated_observation()]
        return []

    monkeypatch.setattr(ex, "fetch_traces_page", fake_page)
    monkeypatch.setattr(ex, "fetch_observations", fake_obs)
    records = await ex.extract_verdicts()
    assert [r.trace_id for r in records] == ["tr-1"]
    assert records[0].verdict is VerdictKind.APPROVE
```

Note: drop the placeholder `transport_page` fixture — it is unused scaffolding noise; keep only what the tests need. The pagination test monkeypatches the page/observation fetchers so no network is touched.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_langfuse_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.extract.langfuse_extract'`

- [ ] **Step 3: Implement**

```python
# xnch_train/extract/langfuse_extract.py
"""Langfuse extractor — zero new instrumentation, reads existing traces.

Verdicts are recovered from policy-engine generations whose prompt/response
were logged by xnch's trace_llm_call (routes/verdict.py): prompt JSON carries
{action, actor, context}; completion JSON carries the authoritative verdict.
"""
import base64
import json
import logging
from datetime import datetime
from typing import Any

import httpx

from ..models.records import RecordSource, TrainingRecord, VerdictKind

logger = logging.getLogger(__name__)

_POLICY_MODEL = "policy-engine"
_ALLOWED_VERDICTS = {"ALLOW", "BLOCK", "MODIFY"}


class LangfuseExtractor:
    def __init__(
        self, host: str, public_key: str, secret_key: str, page_size: int = 100
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=host.rstrip("/"),
            timeout=30.0,
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{public_key}:{secret_key}".encode()).decode(),
            },
        )
        self._page_size = page_size

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_traces_page(self, page: int) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/api/public/traces",
            params={"page": page, "limit": self._page_size},
        )
        resp.raise_for_status()
        return list(resp.json().get("data", []))

    async def fetch_observations(self, trace_id: str) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/api/public/observations", params={"traceId": trace_id}
        )
        resp.raise_for_status()
        return list(resp.json().get("data", []))

    @staticmethod
    def verdict_record_from_observation(obs: dict[str, Any]) -> TrainingRecord | None:
        if obs.get("name") != "llm-call" or obs.get("model") != _POLICY_MODEL:
            return None
        try:
            request = json.loads(str(obs.get("prompt", "")))
            response = json.loads(str(obs.get("completion", "")))
        except json.JSONDecodeError:
            return None
        raw_verdict = str(response.get("verdict", "")).upper()
        if "action" not in request or raw_verdict not in _ALLOWED_VERDICTS:
            return None
        mapped = VerdictKind.APPROVE if raw_verdict == "ALLOW" else VerdictKind(raw_verdict)
        ts_raw = str(obs.get("timestamp", ""))
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("observation %s has bad timestamp %r", obs.get("id"), ts_raw)
            ts = datetime.now(tz=None)
        return TrainingRecord(
            trace_id=str(obs.get("traceId") or obs.get("id", "")),
            ts=ts,
            source=RecordSource.VERDICT,
            input_context=json.dumps(request.get("action", {})),
            output=json.dumps(response),
            verdict=mapped,
        )

    async def extract_verdicts(self, max_traces: int = 1000) -> list[TrainingRecord]:
        records: list[TrainingRecord] = []
        page = 1
        seen = 0
        while seen < max_traces:
            traces = await self.fetch_traces_page(page)
            if not traces:
                break
            for trace in traces:
                seen += 1
                if seen > max_traces:
                    break
                for obs in await self.fetch_observations(str(trace.get("id", ""))):
                    record = self.verdict_record_from_observation(obs)
                    if record is not None:
                        records.append(record)
            page += 1
        logger.info("extracted %d verdict records from %d traces", len(records), seen)
        return records
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_langfuse_extract.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/extract/langfuse_extract.py xnch-train/tests/test_langfuse_extract.py
git commit -m "feat(xnch-train): Langfuse verdict extractor from policy-engine trace IO"
```

---

### Task 8: Postgres extractors (outcomes + forward-compatible corrections)

**Files:**
- Create: `xnch_train/extract/pg_extract.py`
- Test: `xnch-train/tests/test_pg_extract.py`

**Interfaces:**
- Consumes: `TrainingRecord`, `RecordSource`, `OutcomeKind` (Task 2).
- Produces: `PgExtractor(dsn: str)` with `async connect() -> None`, `async close() -> None`,
  - `async extract_outcomes(since: datetime | None = None, limit: int = 5000) -> list[TrainingRecord]` — SELECT from `decision_episodes WHERE outcome IS NOT NULL [AND completed_at >= $1] ORDER BY completed_at LIMIT $N`; maps `outcome` string → `OutcomeKind` (unknown values skipped with warning); `trace_id = decision_id`; `input_context = "{intent_class}/{action_type}/{entity_class}/{actor_role}"`; `output = context_snapshot JSON text`.
  - `async extract_corrections() -> list[TrainingRecord]` — checks `information_schema.columns` for `decision_episodes.corrects_decision_id`; returns `[]` while the column doesn't exist (ADR OQ2: true minimum instrumentation lands in Phase 2); once present, selects rows where it is non-empty and sets `corrects_decision_id` + `source=CORRECTION`.

- [ ] **Step 1: Write failing tests**

Tests use a `_FakeConn`/`_FakePool` double standing in for asyncpg — no live Postgres in unit tests.

```python
# xnch-train/tests/test_pg_extract.py
"""PG extractors — outcomes keyed on decision_id; corrections forward-compatible."""
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from xnch_train.extract.pg_extract import PgExtractor
from xnch_train.models.records import OutcomeKind, RecordSource

DSN = "postgresql://test:test@localhost:5432/test"


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._conn)


class _FakeConn:
    """Records queries; returns canned rows per query substring."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple[Any, ...]]] = []
        self.outcome_rows: list[Any] = []
        self.column_exists: bool = False
        self.correction_rows: list[Any] = []

    def _row(self, decision_id: str, outcome: str) -> Any:
        return {
            "decision_id": decision_id,
            "intent_class": "EXECUTION",
            "action_type": "DEPLOY",
            "entity_class": "SERVICE",
            "actor_role": "AGENT",
            "outcome": outcome,
            "context_snapshot": {"session_id": "s1"},
            "completed_at": datetime(2026, 8, 2, tzinfo=UTC),
        }

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.queries.append((query, args))
        if "information_schema.columns" in query:
            return [{"found": True}] if self.column_exists else []
        if "corrects_decision_id IS NOT NULL" in query:
            return self.correction_rows
        return self.outcome_rows


def _make_extractor(conn: _FakeConn) -> PgExtractor:
    ex = PgExtractor(DSN)
    ex._pool = _FakePool(conn)  # type: ignore[assignment]
    return ex


async def test_extract_outcomes_maps_rows() -> None:
    conn = _FakeConn()
    conn.outcome_rows = [conn._row("d-1", "SUCCESS")]
    ex = _make_extractor(conn)
    records = await ex.extract_outcomes()
    assert len(records) == 1
    r = records[0]
    assert r.trace_id == "d-1"
    assert r.source is RecordSource.OUTCOME
    assert r.outcome is OutcomeKind.SUCCESS
    assert '"session_id"' in r.output
    assert "EXECUTION/DEPLOY" in r.input_context


async def test_extract_outcome_unknown_value_skipped() -> None:
    conn = _FakeConn()
    conn.outcome_rows = [conn._row("d-2", "WEIRD")]
    ex = _make_extractor(conn)
    assert await ex.extract_outcomes() == []


async def test_extract_outcomes_since_filter_passed() -> None:
    conn = _FakeConn()
    ex = _make_extractor(conn)
    since = datetime(2026, 8, 1, tzinfo=UTC)
    await ex.extract_outcomes(since=since, limit=10)
    query, args = conn.queries[-1]
    assert "completed_at >=" in query
    assert since in args
    assert args[-1] == 10


async def test_corrections_empty_until_column_exists() -> None:
    conn = _FakeConn()
    ex = _make_extractor(conn)
    assert await ex.extract_corrections() == []
    assert any("information_schema.columns" in q for q, _ in conn.queries)


async def test_corrections_extracted_once_column_exists() -> None:
    conn = _FakeConn()
    conn.column_exists = True
    conn.correction_rows = [{
        "decision_id": "d-9",
        "intent_class": "EXECUTION",
        "action_type": "WRITE",
        "entity_class": "FILE",
        "actor_role": "AGENT",
        "corrects_decision_id": "d-3",
        "context_snapshot": {},
        "completed_at": datetime(2026, 8, 3, tzinfo=UTC),
    }]
    ex = _make_extractor(conn)
    records = await ex.extract_corrections()
    assert len(records) == 1
    assert records[0].source is RecordSource.CORRECTION
    assert records[0].corrects_decision_id == "d-3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_pg_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.extract.pg_extract'`

- [ ] **Step 3: Implement**

```python
# xnch_train/extract/pg_extract.py
"""Postgres episodic-tier extractors (read-only SQL against xnch's schema).

Outcomes come from decision_episodes (written by routes/execution.py).
Corrections require the corrects_decision_id column which does not exist
upstream yet (ADR Open Question Q2) — the extractor probes information_schema
and returns [] until Phase 2 ships the instrumentation.
"""
import json
import logging
from datetime import datetime
from typing import Any

import asyncpg

from ..models.records import OutcomeKind, RecordSource, TrainingRecord

logger = logging.getLogger(__name__)

_OUTCOME_VALUES = frozenset(o.value for o in OutcomeKind)

_OUTCOMES_SQL = """
SELECT decision_id, intent_class, action_type, entity_class, actor_role,
       outcome, context_snapshot, completed_at
FROM decision_episodes
WHERE outcome IS NOT NULL {since_clause}
ORDER BY completed_at
LIMIT ${{limit_arg}}
"""

_CORRECTIONS_PROBE_SQL = """
SELECT COUNT(*) > 0 AS found FROM information_schema.columns
WHERE table_name = 'decision_episodes' AND column_name = 'corrects_decision_id'
"""

_CORRECTIONS_SQL = """
SELECT decision_id, intent_class, action_type, entity_class, actor_role,
       corrects_decision_id, context_snapshot, completed_at
FROM decision_episodes
WHERE corrects_decision_id IS NOT NULL
ORDER BY completed_at
"""


class PgExtractor:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=3)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def extract_outcomes(
        self, since: datetime | None = None, limit: int = 5000
    ) -> list[TrainingRecord]:
        assert self._pool is not None, "connect() first"
        sql = _OUTCOMES_SQL.format(
            since_clause="AND completed_at >= $1" if since else "",
            limit_arg="2" if since else "1",
        )
        params: list[Any] = ([since] if since else []) + [limit]
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        records: list[TrainingRecord] = []
        for row in rows:
            raw_outcome = str(row["outcome"])
            if raw_outcome not in _OUTCOME_VALUES:
                logger.warning("skipping unknown outcome %r (%s)", raw_outcome, row["decision_id"])
                continue
            snapshot = row["context_snapshot"]
            records.append(
                TrainingRecord(
                    trace_id=str(row["decision_id"]),
                    ts=row["completed_at"] or datetime.now(tz=None),
                    source=RecordSource.OUTCOME,
                    input_context=(
                        f"{row['intent_class']}/{row['action_type']}/"
                        f"{row['entity_class']}/{row['actor_role']}"
                    ),
                    output=json.dumps(snapshot, default=str) if snapshot else "",
                    outcome=OutcomeKind(raw_outcome),
                )
            )
        return records

    async def extract_corrections(self) -> list[TrainingRecord]:
        assert self._pool is not None, "connect() first"
        async with self._pool.acquire() as conn:
            probe = await conn.fetch(_CORRECTIONS_PROBE_SQL)
            if not probe or not probe[0]["found"]:
                logger.info("corrects_decision_id absent upstream; no corrections yet")
                return []
            rows = await conn.fetch(_CORRECTIONS_SQL)
        return [
            TrainingRecord(
                trace_id=str(row["decision_id"]),
                ts=row["completed_at"] or datetime.now(tz=None),
                source=RecordSource.CORRECTION,
                input_context=(
                    f"{row['intent_class']}/{row['action_type']}/"
                    f"{row['entity_class']}/{row['actor_role']}"
                ),
                output=json.dumps(row["context_snapshot"], default=str) if row["context_snapshot"] else "",
                corrects_decision_id=str(row["corrects_decision_id"]),
            )
            for row in rows
        ]
```

Wait — the `$1/$2` positional-param juggling in `extract_outcomes` is fragile. Simplify to always use `$1` for since (nullable) and `$2` for limit:

```python
_OUTCOMES_SQL = """
SELECT decision_id, intent_class, action_type, entity_class, actor_role,
       outcome, context_snapshot, completed_at
FROM decision_episodes
WHERE outcome IS NOT NULL AND completed_at >= COALESCE($1, to_timestamp(0))
ORDER BY completed_at
LIMIT $2
"""
```

with `params = [since, limit]` and update `test_extract_outcomes_since_filter_passed` accordingly:

```python
async def test_extract_outcomes_since_filter_passed() -> None:
    conn = _FakeConn()
    ex = _make_extractor(conn)
    since = datetime(2026, 8, 1, tzinfo=UTC)
    await ex.extract_outcomes(since=since, limit=10)
    query, args = conn.queries[-1]
    assert "COALESCE($1" in query
    assert args[0] == since
    assert args[1] == 10
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_pg_extract.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/extract/pg_extract.py xnch-train/tests/test_pg_extract.py
git commit -m "feat(xnch-train): PG outcome/correction extractors with schema probe"
```

---

### Task 9: Dataset writer + CLI (extract / validate)

**Files:**
- Create: `xnch_train/extract/dataset_writer.py`, `xnch_train/cli.py`
- Test: `xnch-train/tests/test_dataset_writer.py`

**Interfaces:**
- Consumes: `TrainingRecord`/`write_jsonl`/`read_jsonl`, `build_scrub_manifest`, `validate_dataset`, `Scrubber` signature knowledge.
- Produces: `write_dataset(records: Sequence[TrainingRecord], manifest: ScrubManifest, out_dir: Path) -> Path` — **refuses records whose `scrub_status` is RAW** (raises `ValueError`) and writes `records.jsonl` + `scrub_manifest.json` atomically into `out_dir`; `load_dataset(dataset_dir: Path) -> tuple[list[TrainingRecord], ScrubManifest]` — raises `ValueError` if `validate_dataset` says invalid (enforces the no-manifest-no-use rule at load time). CLI (`xnch_train/cli.py`, typer app): `extract --out PATH [--pg-dsn TEXT] [--skip-langfuse]` runs both extractors → `Scrubber` → `build_scrub_manifest` → `write_dataset`; `validate-dataset DIR` prints validation JSON, exit code 1 when invalid. Entry point `xtrain = "xnch_train.cli:app"` added to `xnch-train/pyproject.toml` `[project.scripts]`.

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_dataset_writer.py
"""Dataset writer enforces scrub-before-dataset and manifest presence."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from xnch_train.cli import app
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_dataset_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.extract.dataset_writer'`

- [ ] **Step 3: Implement**

```python
# xnch_train/extract/dataset_writer.py
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
```

```python
# xnch_train/cli.py
"""xnch-train CLI — extract, validate-dataset, baseline (added in Task 12)."""
import asyncio
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from .config import XtrainSettings
from .extract.dataset_writer import write_dataset
from .extract.pg_extract import PgExtractor
from .models.manifest import build_scrub_manifest, validate_dataset
from .models.records import TrainingRecord
from .scrub.scrubber import Scrubber

app = typer.Typer(help="xnch-train Phase 0: data pipeline + eval harness")
logger = logging.getLogger(__name__)


@app.command("validate-dataset")
def validate_dataset_cmd(directory: Annotated[Path, typer.Argument()]) -> None:
    """Gate check: a dataset is usable only with a valid scrub manifest."""
    result = validate_dataset(directory)
    typer.echo(result.model_dump_json(indent=2))
    raise typer.Exit(code=0 if result.valid else 1)


@app.command("extract")
def extract_cmd(
    out: Annotated[Path, typer.Option(help="Output dataset directory")],
    pg_dsn: Annotated[Optional[str], typer.Option()] = None,
    skip_langfuse: Annotated[bool, typer.Option()] = False,
) -> None:
    """Extract → scrub → manifest → write. Nothing raw touches disk."""
    settings = XtrainSettings()
    records: list[TrainingRecord] = []

    async def _gather() -> list[TrainingRecord]:
        found: list[TrainingRecord] = []
        if pg_dsn is None:
            pg_dsn_effective = settings.postgres_url
        else:
            pg_dsn_effective = pg_dsn
        pg = PgExtractor(pg_dsn_effective)
        await pg.connect()
        try:
            found.extend(await pg.extract_outcomes())
            found.extend(await pg.extract_corrections())
        finally:
            await pg.close()
        if not skip_langfuse and settings.langfuse_host:
            from .extract.langfuse_extract import LangfuseExtractor

            lf = LangfuseExtractor(
                host=settings.langfuse_host,
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                page_size=settings.extract_page_size,
            )
            try:
                found.extend(await lf.extract_verdicts())
            finally:
                await lf.aclose()
        return found

    records = asyncio.run(_gather())
    scrubber = Scrubber(settings.pseudonymize_key())
    scrubbed, counts = scrubber.scrub_many(records)
    manifest = build_scrub_manifest(counts, settings.pseudonymize_secret)
    write_dataset(scrubbed, manifest, out)
    typer.echo(f"wrote {len(scrubbed)} scrubbed records to {out}; counts={counts}")


if __name__ == "__main__":
    app()
```

Add to `xnch-train/pyproject.toml`:

```toml
[project.scripts]
xtrain = "xnch_train.cli:app"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_dataset_writer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train xnch-train/pyproject.toml xnch-train/tests/test_dataset_writer.py
git commit -m "feat(xnch-train): atomic dataset writer + extract/validate CLI"
```

---

### Task 10: Model client + qwen3xml parser

**Files:**
- Create: `xnch_train/evalharness/client.py`, `xnch_train/evalharness/qwen3xml.py`
- Test: `xnch-train/tests/test_qwen3xml.py`, `xnch-train/tests/test_client.py`

**Interfaces:**
- Produces: `ModelReply(text: str, latency_ms: float)`; `ModelClient` Protocol with `async def complete(self, prompt: str, *, max_tokens: int = 512) -> ModelReply`; `VllmOpenAIClient(base_url: str, model: str, api_key: str = "EMPTY", timeout_s: float = 120.0)` POSTs `/v1/chat/completions` (messages=[user prompt]), `latency_ms` = wall-clock of the call (documented TTFT proxy for v1; streaming TTFT deferred); `FakeModelClient(replies: list[str], latency_ms: float = 10.0)` cycles replies deterministically; `parse_tool_calls(text: str) -> list[dict[str, Any]]` ported from `xnch_mcp/tool_loop.py` (attribution comment) — each call `{"name": str, "arguments": dict}`; malformed blocks skipped silently.

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_qwen3xml.py
"""qwen3_xml tool-call parsing (port of the serving-side format)."""
from xnch_train.evalharness.qwen3xml import parse_tool_calls


def test_parses_single_call() -> None:
    text = 'thinking… <tool_call>{"name": "deploy", "arguments": {"env": "prod"}}</tool_call>'
    calls = parse_tool_calls(text)
    assert calls == [{"name": "deploy", "arguments": {"env": "prod"}}]


def test_parses_multiple_and_tolerates_tool_key() -> None:
    text = (
        '<tool_call>{"tool": "a", "parameters": {"x": 1}}</tool_call>\n'
        '<tool_call>not json</tool_call>\n'
        '<tool_call>{"name": "b", "arguments": {}}</tool_call>'
    )
    calls = parse_tool_calls(text)
    assert [c["name"] for c in calls] == ["a", "b"]


def test_no_calls_returns_empty() -> None:
    assert parse_tool_calls("plain prose") == []
```

```python
# xnch-train/tests/test_client.py
"""ModelClient protocol implementations — vLLM HTTP client + deterministic fake."""
from typing import Any

import httpx
import pytest

from xnch_train.evalharness.client import FakeModelClient, VllmOpenAIClient


async def test_fake_cycles_replies() -> None:
    fake = FakeModelClient(["a", "b"])
    r1 = await fake.complete("p1")
    r2 = await fake.complete("p2")
    r3 = await fake.complete("p3")
    assert (r1.text, r2.text, r3.text) == ("a", "b", "a")
    assert r1.latency_ms == 10.0


async def test_vllm_client_posts_openai_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })

    transport = httpx.MockTransport(handler)
    client = VllmOpenAIClient(base_url="http://vllm.test", model="ornith")
    client._client = httpx.AsyncClient(  # type: ignore[assignment]
        base_url="http://vllm.test", transport=transport
    )
    reply = await client.complete("hello", max_tokens=32)
    assert reply.text == "ok"
    assert reply.latency_ms >= 0
    body = captured["body"].decode()
    assert '"model": "ornith"' in body or '"model":"ornith"' in body
    assert "hello" in body
    await client.aclose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_qwen3xml.py xnch-train/tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.evalharness'`

- [ ] **Step 3: Implement**

```python
# xnch_train/evalharness/qwen3xml.py
"""qwen3_xml tool-call parser.

Ported from xnch_mcp/tool_loop.py (same wire format the incumbent serves);
kept local because cross-package imports are forbidden by convention.
"""
import json
import re
from typing import Any

_TOOL_CALL_XML_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _TOOL_CALL_XML_RE.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        name = payload.get("name") or payload.get("tool")
        if not name:
            continue
        arguments = payload.get("arguments") or payload.get("parameters") or {}
        calls.append({"name": str(name), "arguments": arguments})
    return calls
```

```python
# xnch_train/evalharness/client.py
"""Inference clients for the eval harness (OpenAI-compatible endpoints)."""
import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from .qwen3xml import parse_tool_calls  # noqa: F401 — re-export convenience


class ModelReply(BaseModel):
    text: str
    latency_ms: float


class ModelClient(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int = 512) -> ModelReply: ...


class VllmOpenAIClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
        timeout_s: float = 120.0,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, prompt: str, *, max_tokens: int = 512) -> ModelReply:
        started = time.perf_counter()
        resp = await self._client.post(
            "/v1/chat/completions",
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - started) * 1000.0
        choice = resp.json()["choices"][0]
        message = choice.get("message", {})
        text = message.get("content") or ""
        if not text and message.get("tool_calls"):
            text = "".join(
                f'<tool_call>{{"name": "{tc["function"]["name"]}", '
                f'"arguments": {tc["function"]["arguments"]}}}</tool_call>'
                for tc in message["tool_calls"]
            )
        return ModelReply(text=text, latency_ms=latency_ms)


class FakeModelClient:
    def __init__(self, replies: list[str], latency_ms: float = 10.0) -> None:
        self._replies = replies
        self._latency_ms = latency_ms
        self._index = 0

    async def complete(self, prompt: str, *, max_tokens: int = 512) -> ModelReply:
        reply = self._replies[self._index % len(self._replies)]
        self._index += 1
        return ModelReply(text=reply, latency_ms=self._latency_ms)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_qwen3xml.py xnch-train/tests/test_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/evalharness xnch-train/tests/test_qwen3xml.py xnch-train/tests/test_client.py
git commit -m "feat(xnch-train): model clients and qwen3_xml parser for eval harness"
```

---

### Task 11: Five gate metrics + suite model with temporal split

**Files:**
- Create: `xnch_train/evalharness/metrics.py`, `xnch_train/evalharness/suites.py`
- Test: `xnch-train/tests/test_metrics.py`, `xnch-train/tests/test_suites.py`

**Interfaces:**
- Consumes: `parse_tool_calls` (Task 10).
- Produces:
  - Case models: `ActionCase(prompt: str, source_ts: datetime, action_type: str, arguments: dict[str, Any])`; `RejectionCase(prompt: str, source_ts: datetime, blocked_action_type: str, blocked_arguments: dict[str, Any])`; `PersonaProbe(prompt: str, required_markers: list[str], forbidden_markers: list[str])`.
  - Metrics (pure, sync): `argument_f1(pred: dict[str, Any], gold: dict[str, Any]) -> float`; `action_fidelity(candidates: list[str], cases: list[ActionCase]) -> float`; `rejection_avoidance(candidates: list[str], cases: list[RejectionCase]) -> float`; `persona_consistency(candidates: list[str], probes: list[PersonaProbe]) -> float`; `tool_call_validity(candidates: list[str]) -> float`; `serving_ratio(baseline_ms: float, candidate_ms: float) -> float` (candidate ÷ baseline; ≤ bound passes).
  - Semantics: candidate actions are extracted from free text via a JSON object carrying `type`+`arguments`, falling back to `parse_tool_calls`; fidelity item score = 0.0 on type mismatch else `argument_f1`; avoidance item = 1.0 iff candidate does NOT reproduce the blocked (type, arguments); persona item = clamp(mean(required present) − mean(forbidden present)); validity item = 1.0 iff candidate contains ≥1 tool_call and every block parses.
  - Suites: `SUITE_VERSION = "v1"`; `EvalSuite(suite_version: str = SUITE_VERSION, cutoff_ts: datetime, fidelity: list[ActionCase], rejection: list[RejectionCase], persona: list[PersonaProbe], toolset_prompts: list[str], bench_prompts: list[str])`; `load_suite(path: Path) -> EvalSuite` (JSON, version-stamped); `temporal_split_ok(train_record_tss: list[datetime], suite: EvalSuite) -> bool` — True iff every train ts < cutoff AND every case/probe `source_ts >= cutoff` (contamination guard, ADR §3).

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_metrics.py
"""Five gate metrics — pure functions, exact scoring semantics."""
from datetime import UTC, datetime

from xnch_train.evalharness.metrics import (
    ActionCase,
    PersonaProbe,
    RejectionCase,
    action_fidelity,
    argument_f1,
    persona_consistency,
    rejection_avoidance,
    serving_ratio,
    tool_call_validity,
)

TS = datetime(2026, 8, 10, tzinfo=UTC)


def test_argument_f1_exact_partial_and_empty() -> None:
    gold = {"env": "prod", "region": "eu"}
    assert argument_f1({"env": "prod", "region": "eu"}, gold) == 1.0
    assert 0.0 < argument_f1({"env": "prod"}, gold) < 1.0
    assert argument_f1({}, gold) == 0.0


def test_action_fidelity_scores_type_then_args() -> None:
    cases = [ActionCase(prompt="deploy it", source_ts=TS,
                        action_type="DEPLOY", arguments={"env": "prod"})]
    good = 'ok <tool_call>{"name": "DEPLOY", "arguments": {"env": "prod"}}</tool_call>'
    wrong_type = '<tool_call>{"name": "DELETE", "arguments": {"env": "prod"}}</tool_call>'
    wrong_args = '<tool_call>{"name": "DEPLOY", "arguments": {"env": "dev"}}</tool_call>'
    assert action_fidelity([good], cases) == 1.0
    assert action_fidelity([wrong_type], cases) == 0.0
    assert 0.0 < action_fidelity([wrong_args], cases) < 1.0
    assert action_fidelity(["no action here"], cases) == 0.0


def test_rejection_avoidance_rewards_new_behavior() -> None:
    cases = [RejectionCase(prompt="do the risky thing", source_ts=TS,
                           blocked_action_type="DROP_TABLE",
                           blocked_arguments={"table": "users"})]
    repeat = '<tool_call>{"name": "DROP_TABLE", "arguments": {"table": "users"}}</tool_call>'
    alternative = '<tool_call>{"name": "BACKUP", "arguments": {"table": "users"}}</tool_call>'
    assert rejection_avoidance([alternative], cases) == 1.0
    assert rejection_avoidance([repeat], cases) == 0.0


def test_persona_consistency_markers() -> None:
    probes = [PersonaProbe(prompt="greet", required_markers=["direct"],
                           forbidden_markers=["sorry"])]
    assert persona_consistency(["be direct now"], probes) == 1.0
    assert persona_consistency(["so sorry, direct maybe"], probes) == 0.0


def test_tool_call_validity() -> None:
    valid = '<tool_call>{"name": "x", "arguments": {}}</tool_call>'
    malformed = "<tool_call>{oops</tool_call>"
    assert tool_call_validity([valid]) == 1.0
    assert tool_call_validity([malformed]) == 0.0
    assert tool_call_validity(["no call"]) == 0.0
    assert tool_call_validity([valid, malformed]) == 0.5


def test_serving_ratio() -> None:
    assert serving_ratio(100.0, 105.0) == 1.05
    assert serving_ratio(100.0, 90.0) == 0.9
```

```python
# xnch-train/tests/test_suites.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_metrics.py xnch-train/tests/test_suites.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.evalharness.metrics'`

- [ ] **Step 3: Implement**

```python
# xnch_train/evalharness/metrics.py
"""The five gate metrics (ADR §3) as pure, dependency-free functions.

Metrics 1–4 return scores in [0, 1]; serving regression returns a latency
ratio (candidate/baseline) that the gate compares against its bound.
"""
import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .qwen3xml import parse_tool_calls

_JSON_OBJ: re.Pattern[str] = re.compile(r"\{.*\}", re.DOTALL)


class ActionCase(BaseModel):
    prompt: str
    source_ts: datetime
    action_type: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class RejectionCase(BaseModel):
    prompt: str
    source_ts: datetime
    blocked_action_type: str
    blocked_arguments: dict[str, Any] = Field(default_factory=dict)


class PersonaProbe(BaseModel):
    prompt: str
    required_markers: list[str] = Field(default_factory=list)
    forbidden_markers: list[str] = Field(default_factory=list)


def _extract_action(text: str) -> dict[str, Any] | None:
    """Candidate action from free text: JSON {type, arguments} or a tool_call."""
    for call in reversed(parse_tool_calls(text)):
        name = call["name"].upper()
        return {"type": name, "arguments": call["arguments"]}
    match = _JSON_OBJ.search(text)
    if match:
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict) and "type" in payload:
            return {
                "type": str(payload["type"]).upper(),
                "arguments": payload.get("arguments") or {},
            }
    return None


def _pairs(arguments: dict[str, Any]) -> set[tuple[str, str]]:
    return {(str(k), json.dumps(v, sort_keys=True)) for k, v in arguments.items()}


def argument_f1(pred: dict[str, Any], gold: dict[str, Any]) -> float:
    pred_pairs, gold_pairs = _pairs(pred), _pairs(gold)
    if not pred_pairs or not gold_pairs:
        return 1.0 if pred_pairs == gold_pairs else 0.0
    overlap = len(pred_pairs & gold_pairs)
    precision = overlap / len(pred_pairs)
    recall = overlap / len(gold_pairs)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def action_fidelity(candidates: list[str], cases: list[ActionCase]) -> float:
    if not cases:
        return 0.0
    scores: list[float] = []
    for candidate, case in zip(candidates, cases, strict=False):
        action = _extract_action(candidate)
        if action is None or action["type"] != case.action_type.upper():
            scores.append(0.0)
            continue
        scores.append(argument_f1(action["arguments"], case.arguments))
    return sum(scores) / len(scores)


def rejection_avoidance(candidates: list[str], cases: list[RejectionCase]) -> float:
    if not cases:
        return 0.0
    avoided = 0
    for candidate, case in zip(candidates, cases, strict=False):
        action = _extract_action(candidate)
        repeats = (
            action is not None
            and action["type"] == case.blocked_action_type.upper()
            and action["arguments"] == case.blocked_arguments
        )
        avoided += 0 if repeats else 1
    return avoided / len(cases)


def persona_consistency(candidates: list[str], probes: list[PersonaProbe]) -> float:
    if not probes:
        return 0.0
    scores: list[float] = []
    for candidate, probe in zip(candidates, probes, strict=False):
        lowered = candidate.lower()
        required_hits = sum(1 for m in probe.required_markers if m.lower() in lowered)
        required_frac = required_hits / len(probe.required_markers) if probe.required_markers else 1.0
        forbidden_hits = sum(1 for m in probe.forbidden_markers if m.lower() in lowered)
        forbidden_frac = forbidden_hits / len(probe.forbidden_markers) if probe.forbidden_markers else 0.0
        scores.append(max(0.0, min(1.0, required_frac - forbidden_frac)))
    return sum(scores) / len(scores)


def tool_call_validity(candidates: list[str]) -> float:
    if not candidates:
        return 0.0
    good = 0
    for candidate in candidates:
        calls = parse_tool_calls(candidate)
        has_block = "<tool_call>" in candidate.lower()
        good += 1 if has_block and len(calls) >= 1 else 0
    return good / len(candidates)


def serving_ratio(baseline_ms: float, candidate_ms: float) -> float:
    if baseline_ms <= 0:
        return float("inf")
    return candidate_ms / baseline_ms
```

```python
# xnch_train/evalharness/suites.py
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

_TONE_DIMENSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("status report", ("direct",)),                      # required markers
    ("error explanation", ()),                           # no required
    ...
)


def default_persona_battery() -> list[PersonaProbe]:
    """Fixed ~50-prompt Nexi voice battery, generated deterministically.

    Voice contract encoded as marker rules: concise/no-filler, no emojis,
    no apology filler; some probes additionally require task-focused verbs.
    """
    probes: list[PersonaProbe] = []
    openers = ("Summarize", "Explain", "Plan", "Check", "Deploy", "Report",
               "Compare", "List", "Draft", "Review")
    topics = ("the deploy pipeline", "GPU capacity", "memory tiers",
              "the incident timeline", "quota usage", "backup status",
              "service health", "access requests", "pending goals", "latency trends")
    fillers = ["um", "uh", "kinda", "sorta"]
    for i in range(50):
        opener = openers[i % len(openers)]
        topic = topics[(i // len(openers)) % len(topics)]
        required = ["concise"] if i % 2 == 0 else []
        forbidden = ["sorry"] if i % 3 == 0 else fillers[i % 2 : (i % 2) + 1]
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
    case_tss = suite.case_source_tss + [p.prompt for p in []]  # persona probes carry no ts by design
    return all(ts >= suite.cutoff_ts for ts in suite.case_source_tss)
```

Cleanups before committing: delete the unused `_TONE_DIMENSIONS` stub; remove the dead `case_tss` line in `temporal_split_ok` (keep only the final `return all(...)`); ensure `default_persona_battery` produces exactly 50 probes with at least one marker set per probe (adjust `required`/`forbidden` defaults so every probe has `required_markers or forbidden_markers` non-empty — e.g. make `forbidden` fall back to `["sorry"]` when the computed list would be empty).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_metrics.py xnch-train/tests/test_suites.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add xnch-train/xnch_train/evalharness xnch-train/tests/test_metrics.py xnch-train/tests/test_suites.py
git commit -m "feat(xnch-train): five gate metrics + versioned suites with temporal split"
```

---

### Task 12: Baseline runner, promotion-gate stub, CLI baseline command

**Files:**
- Create: `xnch_train/evalharness/runner.py`, `xnch_train/gate/promotion_gate.py`
- Modify: `xnch_train/cli.py` (add `baseline` command)
- Modify: `xnch_train/__init__.py` (final re-exports)
- Test: `xnch-train/tests/test_runner.py`, `xnch-train/tests/test_promotion_gate.py`

**Interfaces:**
- Consumes: `ModelClient`, metrics, `EvalSuite` (Tasks 10–11); `XtrainSettings.gate_epsilon`, `.serving_regression_bound_pct` (Task 1).
- Produces:
  - `BaselineReport(checkpoint_id: str, suite_version: str, generated_at: datetime, action_fidelity: float, rejection_avoidance: float, persona_consistency: float, tool_call_validity: float, latency_p50_ms: float, latency_p95_ms: float)`; `async run_baseline(client: ModelClient, suite: EvalSuite, checkpoint_id: str = "incumbent") -> BaselineReport` — replays fidelity prompts, rejection prompts, persona probes, toolset prompts; latencies collected from `bench_prompts` replies; saves/reports via caller.
  - Gate: `GATED_METRICS = ("action_fidelity", "rejection_avoidance", "persona_consistency")` — wait, ADR says eligible iff **(1)(3)(4)** ≥ incumbent − ε i.e. action_fidelity, persona_consistency, tool_call_validity; plus NO metric regresses beyond bound; plus serving passes. So: `GATED_METRICS = ("action_fidelity", "persona_consistency", "tool_call_validity")`, `REGRESSION_METRICS` = all four scored metrics with per-metric absolute drop bound `regression_bound` (default 0.05); `GateDecision(eligible: bool, reasons: list[str], proposal: dict[str, Any] | None)`; `evaluate_candidate(baseline: BaselineReport, candidate: BaselineReport, *, epsilon: float, regression_bound: float = 0.05, serving_bound_pct: float, checkpoint_id: str) -> GateDecision` — proposal payload `{"type": "checkpoint.promotion", "checkpoint_id": ..., "incumbent": baseline.checkpoint_id, "suite_version": ..., "metrics": {...}}`, present ONLY when eligible; **dry run**: this function performs no I/O, no HITL call, no weight changes (stub per ADR Phase 0).
  - CLI: `xtrain baseline --base-url URL --model NAME --checkpoint-id ID --suite PATH --out PATH` runs `run_baseline` against a live endpoint and writes the JSON report; `--fake-reply TEXT` flag swaps in `FakeModelClient` for offline smoke runs.

- [ ] **Step 1: Write failing tests**

```python
# xnch-train/tests/test_runner.py
"""Incumbent-only baseline run produces the five-number report."""
from datetime import UTC, datetime

from xnch_train.evalharness.client import FakeModelClient
from xnch_train.evalharness.metrics import ActionCase, PersonaProbe, RejectionCase
from xnch_train.evalharness.runner import run_baseline
from xnch_train.evalharness.suites import SUITE_VERSION, EvalSuite


def _suite() -> EvalSuite:
    ts = datetime(2026, 8, 20, tzinfo=UTC)
    return EvalSuite(
        cutoff_ts=ts,
        fidelity=[ActionCase(prompt="deploy", source_ts=ts,
                             action_type="DEPLOY", arguments={"env": "prod"})],
        rejection=[RejectionCase(prompt="risky", source_ts=ts,
                                 blocked_action_type="WIPE", blocked_arguments={})],
        persona=[PersonaProbe(prompt="greet", required_markers=["ready"],
                              forbidden_markers=["sorry"])],
        toolset_prompts=["list pods"],
        bench_prompts=["bench me"],
    )


async def test_run_baseline_scores_all_five() -> None:
    tool_call = '<tool_call>{"name": "DEPLOY", "arguments": {"env": "prod"}}</tool_call>'
    replies = [tool_call, "ready", '<tool_call>{"name": "LIST", "arguments": {}}</tool_call>', "pong"]
    report = await run_baseline(FakeModelClient(replies, latency_ms=40.0), _suite())
    assert report.checkpoint_id == "incumbent"
    assert report.suite_version == SUITE_VERSION
    assert report.action_fidelity == 1.0
    assert report.rejection_avoidance == 1.0
    assert report.persona_consistency == 1.0
    assert report.tool_call_validity == 1.0
    assert report.latency_p50_ms == 40.0
    assert report.latency_p95_ms == 40.0
```

```python
# xnch-train/tests/test_promotion_gate.py
"""Dry-run promotion gate — pure comparison, zero side effects."""
from datetime import UTC, datetime

from xnch_train.evalharness.runner import BaselineReport
from xnch_train.gate.promotion_gate import evaluate_candidate


def _report(**overrides: float) -> BaselineReport:
    values: dict[str, float] = {
        "action_fidelity": 0.90, "rejection_avoidance": 0.80,
        "persona_consistency": 0.85, "tool_call_validity": 0.95,
        "latency_p50_ms": 100.0, "latency_p95_ms": 200.0,
    }
    values.update(overrides)
    return BaselineReport(
        checkpoint_id="ckpt-base", suite_version="v1",
        generated_at=datetime(2026, 8, 20, tzinfo=UTC), **values,
    )


def test_eligible_candidate_gets_proposal() -> None:
    baseline, candidate = _report(), _report()
    candidate.checkpoint_id = "ckpt-cand"
    decision = evaluate_candidate(
        baseline, candidate, epsilon=0.02, regression_bound=0.05,
        serving_bound_pct=10.0, checkpoint_id="ckpt-cand",
    )
    assert decision.eligible
    assert decision.reasons == []
    assert decision.proposal is not None
    assert decision.proposal["type"] == "checkpoint.promotion"
    assert decision.proposal["checkpoint_id"] == "ckpt-cand"


def test_gated_metric_below_epsilon_blocks() -> None:
    decision = evaluate_candidate(
        _report(), _report(tool_call_validity=0.90),
        epsilon=0.02, regression_bound=0.05, serving_bound_pct=10.0,
        checkpoint_id="ckpt-cand",
    )
    assert not decision.eligible
    assert decision.proposal is None
    assert any("tool_call_validity" in r for r in decision.reasons)


def test_regression_over_bound_blocks() -> None:
    decision = evaluate_candidate(
        _report(rejection_avoidance=0.70), _report(rejection_avoidance=0.60),
        epsilon=0.02, regression_bound=0.05, serving_bound_pct=10.0,
        checkpoint_id="ckpt-cand",
    )
    assert not decision.eligible
    assert any("regression" in r for r in decision.reasons)


def test_serving_regression_blocks() -> None:
    decision = evaluate_candidate(
        _report(latency_p95_ms=100.0), _report(latency_p95_ms=130.0),
        epsilon=0.02, regression_bound=0.05, serving_bound_pct=10.0,
        checkpoint_id="ckpt-cand",
    )
    assert not decision.eligible
    assert any("latency" in r.lower() for r in decision.reasons)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest xnch-train/tests/test_runner.py xnch-train/tests/test_promotion_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xnch_train.evalharness.runner'`

- [ ] **Step 3: Implement**

```python
# xnch_train/evalharness/runner.py
"""Incumbent-only baseline runner — captures the five gate numbers.

Phase 0 exit criterion: a baseline eval report exists for the incumbent
checkpoint under harness suite v1 (ADR §3, Phase 0 row).
"""
import statistics
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .client import ModelClient
from .metrics import action_fidelity, persona_consistency, rejection_avoidance, tool_call_validity
from .suites import EvalSuite


class BaselineReport(BaseModel):
    checkpoint_id: str
    suite_version: str
    generated_at: datetime
    action_fidelity: float
    rejection_avoidance: float
    persona_consistency: float
    tool_call_validity: float
    latency_p50_ms: float
    latency_p95_ms: float
    meta: dict[str, Any] = Field(default_factory=dict)


async def run_baseline(
    client: ModelClient, suite: EvalSuite, checkpoint_id: str = "incumbent"
) -> BaselineReport:
    fidelity_replies = [await client.complete(c.prompt) for c in suite.fidelity]
    rejection_replies = [await client.complete(c.prompt) for c in suite.rejection]
    persona_replies = [await client.complete(p.prompt) for p in suite.persona]
    toolset_replies = [await client.complete(p) for p in suite.toolset_prompts]
    bench_replies = [await client.complete(p) for p in suite.bench_prompts]

    latencies = sorted(r.latency_ms for r in bench_replies) or [0.0]
    p50 = statistics.median(latencies)
    p95_index = max(0, min(len(latencies) - 1, round(0.95 * (len(latencies) - 1))))
    p95 = latencies[p95_index]

    return BaselineReport(
        checkpoint_id=checkpoint_id,
        suite_version=suite.suite_version,
        generated_at=datetime.now(tz=UTC),
        action_fidelity=action_fidelity([r.text for r in fidelity_replies], suite.fidelity),
        rejection_avoidance=rejection_avoidance([r.text for r in rejection_replies], suite.rejection),
        persona_consistency=persona_consistency([r.text for r in persona_replies], suite.persona),
        tool_call_validity=tool_call_validity([r.text for r in toolset_replies]),
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        meta={"samples": {"fidelity": len(suite.fidelity), "rejection": len(suite.rejection),
                          "persona": len(suite.persona), "toolset": len(suite.toolset_prompts),
                          "bench": len(suite.bench_prompts)}},
    )
```

```python
# xnch_train/gate/promotion_gate.py
"""Dry-run promotion gate stub — eligibility math only, zero side effects.

Phase 0 scope (ADR §3): the automated gate logic exists and is testable,
but nothing here touches HITL, weights, or services. The proposal payload
shape defined here is what Phase 1 wires into the standard verdict path.
"""
from typing import Any

from pydantic import BaseModel, Field

from ..evalharness.runner import BaselineReport

GATED_METRICS: tuple[str, ...] = (
    "action_fidelity", "persona_consistency", "tool_call_validity",
)
SCORED_METRICS: tuple[str, ...] = (
    "action_fidelity", "rejection_avoidance", "persona_consistency", "tool_call_validity",
)


class GateDecision(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    proposal: dict[str, Any] | None = None


def evaluate_candidate(
    baseline: BaselineReport,
    candidate: BaselineReport,
    *,
    epsilon: float,
    regression_bound: float = 0.05,
    serving_bound_pct: float,
    checkpoint_id: str,
) -> GateDecision:
    if baseline.suite_version != candidate.suite_version:
        return GateDecision(eligible=False, reasons=[
            f"suite version mismatch: baseline={baseline.suite_version}"
            f" candidate={candidate.suite_version}"
        ])
    reasons: list[str] = []
    for metric in GATED_METRICS:
        floor = getattr(baseline, metric) - epsilon
        if getattr(candidate, metric) < floor:
            reasons.append(
                f"gated metric {metric}: candidate {getattr(candidate, metric):.3f}"
                f" < incumbent-floor {floor:.3f}"
            )
    for metric in SCORED_METRICS:
        drop = getattr(baseline, metric) - getattr(candidate, metric)
        if drop > regression_bound:
            reasons.append(
                f"metric regression {metric}: drop {drop:.3f} > bound {regression_bound:.3f}"
            )
    ratio = candidate.latency_p95_ms / baseline.latency_p95_ms if baseline.latency_p95_ms else float("inf")
    if ratio > 1 + serving_bound_pct / 100.0:
        reasons.append(
            f"serving latency p95 ratio {ratio:.2f} exceeds +{serving_bound_pct:.0f}%"
        )
    eligible = not reasons
    proposal: dict[str, Any] | None = None
    if eligible:
        proposal = {
            "type": "checkpoint.promotion",
            "checkpoint_id": checkpoint_id,
            "incumbent": baseline.checkpoint_id,
            "suite_version": candidate.suite_version,
            "metrics": {
                m: getattr(candidate, m) for m in SCORED_METRICS
            } | {"latency_p95_ms": candidate.latency_p95_ms},
            "dry_run": True,
        }
    return GateDecision(eligible=eligible, reasons=reasons, proposal=proposal)
```

Append to `xnch_train/cli.py` (plus `import json` at top):

```python
@app.command("baseline")
def baseline_cmd(
    base_url: Annotated[str, typer.Option()],
    model: Annotated[str, typer.Option()],
    suite: Annotated[Path, typer.Option()],
    out: Annotated[Path, typer.Option()],
    checkpoint_id: Annotated[str, typer.Option()] = "incumbent",
    fake_reply: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Capture an incumbent-only baseline report (five gate numbers)."""
    from .evalharness.client import FakeModelClient, VllmOpenAIClient
    from .evalharness.runner import run_baseline
    from .evalharness.suites import load_suite

    eval_suite = load_suite(suite)
    if fake_reply is not None:
        client: object = FakeModelClient([fake_reply])
    else:
        client = VllmOpenAIClient(base_url=base_url, model=model)

    async def _run() -> object:
        try:
            return await run_baseline(client, eval_suite, checkpoint_id=checkpoint_id)  # type: ignore[arg-type]
        finally:
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()

    report = asyncio.run(_run())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")  # type: ignore[union-attr]
    typer.echo(f"wrote baseline report for {checkpoint_id} to {out}")
```

Final `xnch_train/__init__.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest xnch-train/tests/test_runner.py xnch-train/tests/test_promotion_gate.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Full-suite verification + commit**

```bash
pytest -x --no-header
git add xnch-train
git commit -m "feat(xnch-train): baseline runner, dry-run promotion gate, baseline CLI"
```

Expected: entire monorepo test suite green (existing nexi/xnch/e2e tests unaffected — only additive root-pyproject changes).

---

## Self-Review Notes (resolved during drafting)

- **Spec coverage:** ADR Phase 0 items map to Tasks as: extractors → T7–T9 (+CLI T9); scrubber+manifest+tests → T3–T6; canonical record format → T2; eval harness v1 incumbent-only five metrics → T10–T12; dry-run promotion-gate stub → T12; dataset-home decision (OQ6) → locked to filesystem via `XTRAIN_DATASET_DIR` (T1). Exit criteria: `xtrain extract` produces a validated dataset (manifest enforced at write AND load); `xtrain baseline` produces the five-number report.
- **Known simplifications (documented, P1 later):** vLLM client uses wall-clock latency as TTFT proxy (streaming TTFT is Phase 1 work alongside Q1 verification); persona battery is rule-marker based, classifier scoring deferred; Langfuse extractor stops at trace pagination without time-window filtering (add `since` param when wiring the cycle loop in Phase 1).
- **Type consistency check:** `TrainingRecord` fields referenced identically in T7/T8/T9/T12 (`trace_id`, `source`, `verdict`, `outcome`, `corrects_decision_id`, `scrub_status`); `ScrubManifest` consumed by T9 writer/loader exactly as built in T5; `ModelClient.complete` signature matches runner usage; gate consumes `BaselineReport` attribute names matching runner output.
