"""Tests for exec MCP handler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from xnch_mcp.context import ActorContext
from xnch_mcp.exec.policy import load_exec_policy
from xnch_mcp.exec.service import ExecRunService
from xnch_mcp.handlers import exec as exec_handlers
from xnch_mcp.registry import list_tools_for_actor


@pytest.fixture
def exec_setup(tmp_path: Path) -> ExecRunService:
    cfg = tmp_path / "exec-policy.yaml"
    cfg.write_text(
        """
defaults:
  working_dir: /home/x-nch/xnchSystems
denied_substrings: [";"]
hosts:
  node-a:
    allowed_prefixes: ["hostname"]
  node-b:
    allowed_prefixes: ["hostname"]
"""
    )
    policy = load_exec_policy(cfg)
    return ExecRunService(policy, local_host="node-a")


@pytest.mark.asyncio
async def test_handler_run(exec_setup: ExecRunService) -> None:
    app = MagicMock()
    app.fs_read_service = MagicMock()
    app.exec_run_service = exec_setup
    app.event_log = MagicMock()
    app.event_log.emit = MagicMock()
    actor = ActorContext(actor_role="nexi", trace_id="t1")
    result = await exec_handlers._exec_run(
        app, actor, {"host": "node-a", "command": "hostname"}
    )
    assert result["exit_code"] == 0
    assert result["stdout"].strip()


def test_exec_tool_nexi_only() -> None:
    nexi = {t.name for t in list_tools_for_actor("nexi")}
    open_code = {t.name for t in list_tools_for_actor("opencode")}
    assert "xnch_exec_run" in nexi
    assert "xnch_exec_run" not in open_code


@pytest.mark.asyncio
async def test_remote_dispatch(exec_setup: ExecRunService) -> None:
    remote = AsyncMock()
    remote.run = AsyncMock(return_value={"host": "node-b", "exit_code": 0, "stdout": "xnch-core"})
    exec_setup._remote["node-b"] = remote
    result = await exec_setup.run("node-b", "hostname")
    assert result["stdout"] == "xnch-core"
