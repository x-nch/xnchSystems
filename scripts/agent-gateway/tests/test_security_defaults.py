"""Security-default tests (2026-08-24 audit F8 / reconciliation A3).

The gateway spawns coding-agent CLIs; its defaults must be deny-by-default:
1. opencode_auto_approve defaults False (no silent `--auto`)
2. _verify_api_key fails CLOSED when no api_key configured (503), not open
3. spawned children receive an allowlisted env, never the full service env
"""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi import HTTPException

from agent_gateway.adapters.base import AgentRequest, child_env
from agent_gateway.adapters.opencode import OpenCodeAdapter
from agent_gateway.config import Settings
from agent_gateway.main import _verify_api_key


def test_default_auto_approve_is_off() -> None:
    assert Settings().opencode_auto_approve is False


def test_verify_api_key_fails_closed_when_unset(monkeypatch) -> None:
    from agent_gateway.config import settings

    monkeypatch.setattr(settings, "api_key", None)
    with pytest.raises(HTTPException) as exc:
        _verify_api_key(None)
    assert exc.value.status_code == 503

    with pytest.raises(HTTPException) as exc_bearer:
        _verify_api_key("Bearer whatever")
    assert exc_bearer.value.status_code == 503


def test_verify_api_key_rejects_wrong_token(monkeypatch) -> None:
    from agent_gateway.config import settings

    monkeypatch.setattr(settings, "api_key", "right")
    with pytest.raises(HTTPException) as exc:
        _verify_api_key("Bearer wrong")
    assert exc.value.status_code == 401


def test_child_env_allowlist_drops_secrets() -> None:
    dirty = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/Users/xnch",
        "AGENT_GATEWAY_API_KEY": "secret",
        "DATABASE_URL": "postgres://...",
        "HTTP_PROXY": "http://evil:3128",
    }
    env = child_env(dirty)
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == "/Users/xnch"
    for banned in ("AGENT_GATEWAY_API_KEY", "DATABASE_URL", "HTTP_PROXY"):
        assert banned not in env


def test_run_passes_scoped_env_to_subprocess(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    real_exec = asyncio.create_subprocess_exec

    def spy(*args, **kwargs):
        captured["env"] = kwargs.get("env")
        return real_exec(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spy)

    adapter = OpenCodeAdapter()
    request = AgentRequest(prompt="hi", model=None)
    settings_like = {"opencode_cli": "/bin/echo"}
    monkeypatch.setattr(
        "agent_gateway.adapters.opencode.settings.opencode_cli",
        settings_like["opencode_cli"],
    )
    monkeypatch.setattr(
        "agent_gateway.adapters.opencode.settings.opencode_auto_approve", False
    )

    async def scenario() -> None:
        await adapter.run(request, timeout_seconds=10)

    asyncio.run(scenario())

    env = captured.get("env")
    assert env is not None, "spawn must pass an explicit env allowlist"
    assert "PATH" in env and "HOME" in env