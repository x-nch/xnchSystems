"""Auth fail-closed tests for the node-b sidecar agents (exec-agent, fs-read-agent).

Prior behavior: `_verify_token` returned silently when the expected token env
was unset — an unauthenticated 0.0.0.0-bound command/filesystem service.
Required behavior (2026-08-24 audit F4):
- unconfigured token -> 503 (loud misconfiguration, service refuses to authorize)
- missing/wrong token -> 401, constant-time compare
- correct token -> passes
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def agents(monkeypatch):
    exec_srv = _load("exec_agent_server_auth", "exec_agent/server.py")
    fs_srv = _load("fs_read_agent_server_auth", "fs_read_agent/server.py")
    return exec_srv, fs_srv


def _token_of(module: Any):
    """Return the settings attribute name the module checks."""
    return module


@pytest.mark.parametrize("which", [0, 1])
def test_unconfigured_token_fails_closed(agents, monkeypatch, which: int) -> None:
    exec_srv, fs_srv = agents
    srv = (exec_srv, fs_srv)[which]
    attr = "exec_agent_token" if which == 0 else "fs_agent_token"
    monkeypatch.setattr(srv.xnch_settings, attr, None)
    with pytest.raises(HTTPException) as exc:
        srv._verify_token(None)
    assert exc.value.status_code == 503


@pytest.mark.parametrize("which", [0, 1])
def test_wrong_token_401(agents, monkeypatch, which: int) -> None:
    exec_srv, fs_srv = agents
    srv = (exec_srv, fs_srv)[which]
    attr = "exec_agent_token" if which == 0 else "fs_agent_token"
    monkeypatch.setattr(srv.xnch_settings, attr, "correct-token")
    with pytest.raises(HTTPException) as exc:
        srv._verify_token("wrong-token")
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc_missing:
        srv._verify_token(None)
    assert exc_missing.value.status_code == 401


@pytest.mark.parametrize("which", [0, 1])
def test_correct_token_passes(agents, monkeypatch, which: int) -> None:
    exec_srv, fs_srv = agents
    srv = (exec_srv, fs_srv)[which]
    attr = "exec_agent_token" if which == 0 else "fs_agent_token"
    monkeypatch.setattr(srv.xnch_settings, attr, "correct-token")
    assert srv._verify_token("correct-token") is None
