"""Immutable checkpoint registry + retention (Node B NVMe hygiene)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Checkpoint IDs are strings. The eval-harness promotion gate emits a
# `checkpoint.promotion` proposal keyed by `checkpoint_id`; that id is the
# immutable primary key of this registry (Gate G2 alignment).
CheckpointID = str


class CheckpointRegistry:
    """Register immutable checkpoint ids and enforce NVMe retention.

    The brief's mandated tests require the following semantics (reconciled
    from an internally-inconsistent brief):

    * `current()` returns the NEWEST checkpoint ordered by
      (date DESC, rowid DESC) — NOT `WHERE current=1`. The brief's
      `register()` never sets `current=1`, so a `WHERE current=1` read would
      always return None and fail the `reg.current() == "ckpt-3"` assertion.
    * `retain(max_candidates)` keeps the `max_candidates` newest checkpoints
      and DELETES the rest, returning the evicted ids. With 3 checkpoints and
      max_candidates=2 it keeps ckpt-3 + ckpt-2 and evicts ckpt-1, satisfying
      `assert "ckpt-1" in evicted`.

    The `current` column is retained in CREATE TABLE for forward-compat:
    Task 5/6 promotion will set it on the deployed checkpoint. It is NOT used
    by `current()` today. `checkpoint_id` is the PRIMARY KEY, so a duplicate
    register raises `sqlite3.IntegrityError` (immutable id contract).
    """

    def __init__(self, db: Path) -> None:
        self._db = db
        self._conn = sqlite3.connect(db)
        self._conn.executescript(
            "CREATE TABLE IF NOT EXISTS checkpoints("
            " checkpoint_id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE,"
            " date TEXT NOT NULL, current INTEGER NOT NULL DEFAULT 0);"
        )
        self._conn.commit()

    def register(self, checkpoint_id: str, path: Path, date: str) -> str:
        """Insert an immutable checkpoint id. Raises sqlite3.IntegrityError on a duplicate id."""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR ABORT INTO checkpoints(checkpoint_id,path,date) VALUES(?,?,?)",
            (checkpoint_id, str(path), date),
        )
        self._conn.commit()
        return checkpoint_id

    def current(self) -> str | None:
        """Return the newest checkpoint id by (date DESC, rowid DESC), or None if empty."""
        row = self._conn.execute(
            "SELECT checkpoint_id FROM checkpoints ORDER BY date DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def retain(self, max_candidates: int = 2) -> list[str]:
        """Keep the `max_candidates` newest checkpoints; evict (delete) the rest.

        Returns the list of evicted checkpoint ids (oldest first).
        """
        cur = self._conn.cursor()
        keep = [
            r[0]
            for r in self._conn.execute(
                "SELECT checkpoint_id FROM checkpoints ORDER BY date DESC, rowid DESC LIMIT ?",
                (max_candidates,),
            )
        ]
        evicted = [
            r[0]
            for r in self._conn.execute(
                "SELECT checkpoint_id FROM checkpoints WHERE checkpoint_id NOT IN "
                "(SELECT checkpoint_id FROM checkpoints ORDER BY date DESC, rowid DESC LIMIT ?)",
                (max_candidates,),
            )
        ]
        for cid in evicted:
            cur.execute("DELETE FROM checkpoints WHERE checkpoint_id=?", (cid,))
        self._conn.commit()
        return evicted

    def quota_warning(self, threshold_pct: float = 90.0) -> bool:
        # dummy until Task 7 wires shutil.disk_usage on XTRAIN_CHECKPOINT_DIR parent.
        return False
