"""Tests for filesystem path policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from xnch_mcp.fs.policy import FsAccessDenied, load_fs_policy


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    root = tmp_path / "home"
    root.mkdir()
    secrets = root / ".xnch"
    secrets.mkdir()
    (secrets / "xnch.env").write_text("SECRET=1")
    (root / "readme.txt").write_text("hello")

    cfg = tmp_path / "policy.yaml"
    cfg.write_text(
        f"""
hosts:
  node-a:
    roots:
      - {root}
deny_globs:
  - "**/.ssh/**"
  - "**/keys/**"
  - "**/*.pem"
  - "**/xnch.env"
  - "**/nexi.env"
"""
    )
    return cfg


def test_load_policy(policy_file: Path) -> None:
    policy = load_fs_policy(policy_file)
    assert "node-a" in policy.hosts


def test_resolve_relative(policy_file: Path) -> None:
    policy = load_fs_policy(policy_file)
    resolved = policy.resolve("node-a", "readme.txt")
    assert resolved.name == "readme.txt"


def test_deny_traversal(policy_file: Path) -> None:
    policy = load_fs_policy(policy_file)
    with pytest.raises(FsAccessDenied):
        policy.resolve("node-a", "../etc/passwd")


def test_deny_secrets(policy_file: Path) -> None:
    policy = load_fs_policy(policy_file)
    with pytest.raises(FsAccessDenied):
        policy.resolve("node-a", ".xnch/xnch.env")


def test_unknown_host(policy_file: Path) -> None:
    policy = load_fs_policy(policy_file)
    with pytest.raises(FsAccessDenied):
        policy.resolve("node-z", "readme.txt")
