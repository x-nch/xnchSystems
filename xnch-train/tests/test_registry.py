import sqlite3

import pytest

from xnch_train.train.registry import CheckpointRegistry


def test_registry_immutable_ids_reject_duplicate(tmp_path):
    reg = CheckpointRegistry(tmp_path / "reg.sqlite")
    reg.register("ckpt-1", tmp_path / "p1", "2026-08-27")
    with pytest.raises(sqlite3.IntegrityError):
        reg.register("ckpt-1", tmp_path / "p1b", "2026-08-27")  # immutable id


def test_registry_retention_keeps_current_plus_newest(tmp_path):
    reg = CheckpointRegistry(tmp_path / "reg2.sqlite")
    reg.register("ckpt-1", tmp_path / "p1", "2026-08-27")
    reg.register("ckpt-2", tmp_path / "p2", "2026-08-28")
    reg.register("ckpt-3", tmp_path / "p3", "2026-08-29")
    evicted = reg.retain(max_candidates=2)   # keep current + 2 newest
    assert "ckpt-1" in evicted
    assert reg.current() == "ckpt-3"
