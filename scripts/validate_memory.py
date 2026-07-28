"""Validate memory migration — compare old vs new stores."""
import asyncio
import os
from pathlib import Path

import aiosqlite
from langgraph.store.postgres import PostgresStore

DATABASE_URL = os.environ.get("XNCH_POSTGRES_URL", "postgresql://localhost:5432/xnch")


def validate():
    store = PostgresStore.from_conn_string(DATABASE_URL)

    async def count_old_episodes():
        db_path = Path.home() / ".xnch" / "episodes.db"
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT count(*) FROM episodes") as cursor:
                return (await cursor.fetchone())[0]

    old_count = asyncio.run(count_old_episodes())
    new_episodes = store.search(("episodes",), limit=10000)
    new_count = len(new_episodes)

    async def count_old_patterns():
        db_path = Path.home() / ".xnch" / "patterns.db"
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT count(*) FROM patterns") as cursor:
                return (await cursor.fetchone())[0]

    old_pattern_count = asyncio.run(count_old_patterns())
    new_patterns = store.search(("patterns",), limit=10000)
    new_pattern_count = len(new_patterns)

    print(f"Episodes: old={old_count}, new={new_count}")
    print(f"Patterns: old={old_pattern_count}, new={new_pattern_count}")

    if old_count == new_count and old_pattern_count == new_pattern_count:
        print("VALIDATION PASSED: Counts match")
    else:
        print("VALIDATION FAILED: Counts mismatch")


if __name__ == "__main__":
    validate()
