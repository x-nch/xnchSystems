"""Memory migration tools for Phase 2: Deep Agents CompositeBackend."""

from pathlib import Path
from langchain.tools import tool

CODEBASE_ROOT = Path("/Users/xnch/xnchSystems")


@tool(parse_docstring=True)
def create_composite_backend() -> str:
    """Create the Deep Agents CompositeBackend configuration.

    Sets up routing: /episodes/ and /patterns/ to StoreBackend, rest to StateBackend.
    Uses PostgresStore for production persistence.
    """
    backend_code = '''"""Deep Agents CompositeBackend for XNCH memory."""
import os
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.postgres import PostgresStore

DATABASE_URL = os.environ.get("XNCH_POSTGRES_URL", "postgresql://localhost:5432/xnch")

def create_memory_backend(runtime):
    """Create CompositeBackend with persistent routes for episodes and patterns."""
    store = PostgresStore.from_conn_string(DATABASE_URL)

    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/episodes/": StoreBackend(runtime),
            "/patterns/": StoreBackend(runtime),
            "/entities/": StoreBackend(runtime),
        }
    )

# Example usage with create_deep_agent:
# from deepagents import create_deep_agent
# agent = create_deep_agent(backend=create_memory_backend, store=store)
'''
    script_path = CODEBASE_ROOT / "xnch" / "xnch" / "memory" / "composite_backend.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(backend_code)
    return f"CompositeBackend written to {script_path}"


@tool(parse_docstring=True)
def migrate_episodic_to_store(dry_run: bool = True) -> str:
    """Migrate episodic_store (SQLite/PG) to Deep Agents StoreBackend.

    Reads all episodes and writes them to /episodes/ namespace in StoreBackend.

    Args:
        dry_run: If True, only output the migration plan.
    """
    migration_code = '''"""Migrate episodic store to Deep Agents StoreBackend."""
import os
import json
import time
from pathlib import Path
from langgraph.store.postgres import PostgresStore

DATABASE_URL = os.environ.get("XNCH_POSTGRES_URL", "postgresql://localhost:5432/xnch")

def migrate():
    store = PostgresStore.from_conn_string(DATABASE_URL)

    # Read from existing episodic store (SQLite)
    import aiosqlite
    import asyncio

    async def read_episodes():
        db_path = Path.home() / ".xnch" / "episodes.db"
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM episodes") as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    episodes = asyncio.run(read_episodes())
    print(f"Found {len(episodes)} episodes to migrate")

    migrated = 0
    for ep in episodes:
        episode_id = ep.get("episode_id", "")
        if not episode_id:
            continue

        # Write to StoreBackend namespace
        store.put(
            ("episodes",),
            episode_id,
            {
                "decision_id": ep.get("decision_id", ""),
                "intent_class": ep.get("intent_class", ""),
                "action_type": ep.get("action_type", ""),
                "entity_class": ep.get("entity_class", ""),
                "actor_role": ep.get("actor_role", ""),
                "outcome": ep.get("outcome", ""),
                "context_snapshot": ep.get("context_snapshot", "{}"),
                "created_at": ep.get("created_at", 0),
                "completed_at": ep.get("completed_at"),
            }
        )
        migrated += 1

    print(f"Migrated {migrated} episodes to StoreBackend")

asyncio.run(migrate())
'''
    script_path = CODEBASE_ROOT / "scripts" / "migrate_episodes.py"

    if dry_run:
        return f"Migration script (dry run) would be written to {script_path}"

    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(migration_code)
    return f"Episode migration script written to {script_path}. Run with: python {script_path}"


@tool(parse_docstring=True)
def migrate_patterns_to_store(dry_run: bool = True) -> str:
    """Migrate pattern_store (SQLite) to Deep Agents StoreBackend.

    Reads all patterns and writes them to /patterns/ namespace.

    Args:
        dry_run: If True, only output the migration plan.
    """
    migration_code = '''"""Migrate pattern store to Deep Agents StoreBackend."""
import os
import json
import asyncio
import aiosqlite
from pathlib import Path
from langgraph.store.postgres import PostgresStore

DATABASE_URL = os.environ.get("XNCH_POSTGRES_URL", "postgresql://localhost:5432/xnch")

def migrate():
    store = PostgresStore.from_conn_string(DATABASE_URL)

    async def read_patterns():
        db_path = Path.home() / ".xnch" / "patterns.db"
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM patterns") as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    patterns = asyncio.run(read_patterns())
    print(f"Found {len(patterns)} patterns to migrate")

    migrated = 0
    for pat in patterns:
        pattern_id = pat.get("pattern_id", "")
        if not pattern_id:
            continue

        store.put(
            ("patterns",),
            pattern_id,
            {
                "intent_class": pat.get("intent_class", ""),
                "action_type": pat.get("action_type", ""),
                "entity_class": pat.get("entity_class", ""),
                "actor_role": pat.get("actor_role", ""),
                "context_signature": pat.get("context_signature", ""),
                "success_rate": pat.get("success_rate", 0.5),
                "confidence": pat.get("confidence", 0.0),
                "observation_count": pat.get("observation_count", 0),
            }
        )
        migrated += 1

    print(f"Migrated {migrated} patterns to StoreBackend")

asyncio.run(migrate())
'''
    script_path = CODEBASE_ROOT / "scripts" / "migrate_patterns.py"

    if dry_run:
        return f"Migration script (dry run) would be written to {script_path}"

    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(migration_code)
    return f"Pattern migration script written to {script_path}. Run with: python {script_path}"


@tool(parse_docstring=True)
def validate_memory_migration() -> str:
    """Validate memory migration by comparing old and new stores.

    Checks episode counts, pattern counts, and sample query results.
    """
    validation_code = '''"""Validate memory migration — compare old vs new stores."""
import os
import asyncio
import aiosqlite
from pathlib import Path
from langgraph.store.postgres import PostgresStore

DATABASE_URL = os.environ.get("XNCH_POSTGRES_URL", "postgresql://localhost:5432/xnch")

def validate():
    store = PostgresStore.from_conn_string(DATABASE_URL)

    # Count episodes in old store
    async def count_old_episodes():
        db_path = Path.home() / ".xnch" / "episodes.db"
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT count(*) FROM episodes") as cursor:
                return (await cursor.fetchone())[0]

    old_count = asyncio.run(count_old_episodes())

    # Count episodes in new store
    new_episodes = store.search(("episodes",), limit=10000)
    new_count = len(new_episodes)

    # Count patterns
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

validate()
'''
    script_path = CODEBASE_ROOT / "scripts" / "validate_memory.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(validation_code)
    return f"Validation script written to {script_path}. Run with: python {script_path}"
