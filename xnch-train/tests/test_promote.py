"""Tests for the checkpoint promotion path (Task 6, fake mode).

Covers the symlink flip and the smoke-failure rollback. No GPU, no systemd,
no live vLLM — `_run_smoke` is monkeypatched to raise to exercise rollback.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from xnch_train.train.promote import promote
from xnch_train.train.registry import CheckpointRegistry


def _make_registry(db: Path, entries: dict[str, Path]) -> CheckpointRegistry:
    reg = CheckpointRegistry(db)
    for cid, path in entries.items():
        path.mkdir(parents=True, exist_ok=True)
        reg.register(cid, path, "2026-08-27")
    return reg


def test_promote_flips_symlink(tmp_path: Path) -> None:
    dir_a = tmp_path / "ckpt-1-dir"
    dir_b = tmp_path / "ckpt-2-dir"
    db = tmp_path / "registry.sqlite"
    _make_registry(db, {"ckpt-1": dir_a, "ckpt-2": dir_b})

    link = tmp_path / "current"
    promote("ckpt-2", registry_db=db, current_link=link, fake=True)

    assert link.is_symlink()
    assert Path(os.readlink(link)) == dir_b


def test_promote_rollback_on_smoke_failure(tmp_path: Path, monkeypatch) -> None:
    import importlib

    promote_mod = importlib.import_module("xnch_train.train.promote")

    dir_a = tmp_path / "ckpt-1-dir"
    dir_b = tmp_path / "ckpt-2-dir"
    db = tmp_path / "registry.sqlite"
    _make_registry(db, {"ckpt-1": dir_a, "ckpt-2": dir_b})

    link = tmp_path / "current"
    link.symlink_to(dir_a)

    def _boom(_: Path) -> None:
        raise AssertionError("simulated smoke failure")

    monkeypatch.setattr(promote_mod, "_run_smoke", _boom)

    with pytest.raises(Exception):
        promote("ckpt-2", registry_db=db, current_link=link, fake=True)

    # Smoke failed -> rolled back to prior (ckpt-1) target, never stuck on ckpt-2.
    assert link.is_symlink()
    assert Path(os.readlink(link)) == dir_a
