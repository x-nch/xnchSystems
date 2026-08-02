#!/usr/bin/env python
"""Backfill SQLite episodic memory (decision episodes + patterns) into PG.

One-off migration for the four-tier memory layer: the ad hoc SQLite
EpisodicStore/PatternStore data moves to Postgres (episodes become
decision_episodes; patterns stay patterns). Conversational episodes that
lived in agentmemory/ChromaDB are intentionally NOT migrated (the exact
store holds the real history; the semantic index starts fresh).

Idempotent: rows already present in PG are skipped.

Usage:
    python scripts/backfill_memory_pg.py [sqlite_path]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from xnch.config import settings


def _to_pg_ts(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


async def backfill(db_path: Path, dsn: str) -> dict[str, int]:
    counts = {"decision_episodes": 0, "patterns": 0, "actors": 0}
    pg = await asyncpg.connect(dsn)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT episode_id, decision_id, intent_class, action_type,
                      entity_class, actor_role, outcome, prediction_delta,
                      early_reextraction_flag, context_snapshot,
                      generation_path, created_at, completed_at
               FROM episodes"""
        ) as cursor:
            episodes = await cursor.fetchall()

        for ep in episodes:
            result = await pg.execute(
                """INSERT INTO decision_episodes
                     (episode_id, decision_id, intent_class, action_type,
                      entity_class, actor_role, outcome, prediction_delta,
                      early_reextraction_flag, context_snapshot,
                      generation_path, created_at, completed_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13)
                   ON CONFLICT (episode_id) DO NOTHING""",
                ep["episode_id"], ep["decision_id"], ep["intent_class"],
                ep["action_type"], ep["entity_class"], ep["actor_role"],
                ep["outcome"], ep["prediction_delta"],
                bool(ep["early_reextraction_flag"]),
                ep["context_snapshot"] or None,
                ep["generation_path"] or "MODEL",
                _to_pg_ts(ep["created_at"]), _to_pg_ts(ep["completed_at"]),
            )
            if result == "INSERT 0 1":
                counts["decision_episodes"] += 1

        async with db.execute(
            """SELECT pattern_id, context_signature, intent_class, action_type,
                      entity_class, actor_role, success_rate, confidence,
                      observation_count, avg_prediction_delta,
                      extraction_run_id, created_at, updated_at
               FROM patterns"""
        ) as cursor:
            patterns = await cursor.fetchall()

        for pat in patterns:
            result = await pg.execute(
                """INSERT INTO patterns
                     (pattern_id, context_signature, intent_class, action_type,
                      entity_class, actor_role, success_rate, confidence,
                      observation_count, avg_prediction_delta,
                      extraction_run_id, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                   ON CONFLICT (pattern_id) DO NOTHING""",
                pat["pattern_id"], pat["context_signature"], pat["intent_class"],
                pat["action_type"], pat["entity_class"], pat["actor_role"],
                pat["success_rate"], pat["confidence"], pat["observation_count"],
                pat["avg_prediction_delta"], pat["extraction_run_id"],
                _to_pg_ts(pat["created_at"]), _to_pg_ts(pat["updated_at"]),
            )
            if result == "INSERT 0 1":
                counts["patterns"] += 1

    await pg.close()
    return counts


def main() -> int:
    db_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else settings.db_path
    if not db_path.exists():
        print(f"SQLite DB not found: {db_path}")
        return 1

    dsn = settings.postgres_url
    print(f"source: {db_path}")
    print(f"target: {dsn}")

    import asyncio

    counts = asyncio.run(backfill(db_path, dsn))
    print("backfilled:", json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
