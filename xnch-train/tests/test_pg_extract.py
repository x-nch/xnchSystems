# xnch-train/tests/test_pg_extract.py
"""PG extractors — outcomes keyed on decision_id; corrections forward-compatible."""
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from xnch_train.extract.pg_extract import PgExtractor
from xnch_train.models.records import OutcomeKind, RecordSource

DSN = "postgresql://test:test@localhost:5432/test"


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
    assert "COALESCE($1" in query
    assert args[0] == since
    assert args[1] == 10


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
