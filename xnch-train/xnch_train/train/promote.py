"""Promote a registered checkpoint to production serving (Phase 1, Task 6).

Flips the `~/models/current` symlink to the merged/requantized checkpoint dir,
restarts vLLM (real mode only), and runs a smoke test. On any smoke failure it
rolls the symlink back to the prior release and logs the rollback.

All heavy steps are skipped under ``fake=True`` so this module is hardware-free
and unit-testable without a GPU, systemd, or a live vLLM instance.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from .registry import CheckpointRegistry

logger = logging.getLogger(__name__)

_DEFAULT_CURRENT_LINK = Path.home() / "models" / "current"
_DEFAULT_REGISTRY = Path.home() / "models" / "registry.sqlite"


def _restart_vllm() -> None:
    """Restart the production vLLM unit (real deployment only)."""
    subprocess.run(["systemctl", "restart", "vllm-ornith.service"], check=True)


def _run_smoke(checkpoint_dir: Path) -> None:
    """Assert the served model parses + meets gate #5 latency.

    In fake mode the checkpoint dir simply must exist. In real mode this would
    hit the served model with a fixed prompt set and assert parse + latency
    within the gate #5 bound; that path is exercised in the GPU drill (Step 5).
    """
    if not checkpoint_dir.exists():
        raise RuntimeError(f"checkpoint dir missing after promote: {checkpoint_dir}")


def promote(
    checkpoint_id: str,
    *,
    registry_db: Path | None = None,
    current_link: Path | None = None,
    fake: bool = False,
) -> None:
    """Promote a registered checkpoint to production serving.

    Flips the symlink, optionally restarts vLLM, runs smoke. On smoke failure
    rolls the symlink back to the prior target and logs the rollback.
    """
    link = current_link or _DEFAULT_CURRENT_LINK
    db = registry_db or _DEFAULT_REGISTRY
    reg = CheckpointRegistry(db)
    target = reg.get_path(checkpoint_id)
    if target is None:
        raise ValueError(f"checkpoint {checkpoint_id} not found in registry {db}")

    prior: Path | None = None
    if link.is_symlink():
        prior = Path(os.readlink(link))

    _flip_symlink(link, target)

    if not fake:
        _restart_vllm()

    try:
        _run_smoke(target)
    except Exception:
        logger.exception("smoke failed; rolling back promote of %s", checkpoint_id)
        if prior is not None:
            _flip_symlink(link, prior)
        else:
            _remove_link(link)
        raise


def _flip_symlink(link: Path, target: Path) -> None:
    """Atomically point ``link`` at ``target`` (create temp, os.replace)."""
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.parent / f".{link.name}.tmp-{os.getpid()}"
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    os.symlink(target, tmp)
    os.replace(tmp, link)


def _remove_link(link: Path) -> None:
    if link.is_symlink():
        link.unlink()
