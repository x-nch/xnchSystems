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
WHERE outcome IS NOT NULL AND completed_at >= COALESCE($1, to_timestamp(0))
ORDER BY completed_at
LIMIT $2
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
        params: list[Any] = [since, limit]
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_OUTCOMES_SQL, *params)
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
