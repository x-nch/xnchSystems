"""Integration tests for MCP bridge pool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from xnch_mcp.bridge.config import load_bridge_config
from xnch_mcp.bridge.pool import McpBridgePool, set_bridge_pool
from xnch_mcp.context import ActorContext
from xnch_mcp.registry import invoke_tool, list_tools_for_actor


@pytest.fixture
def mock_bridge_config(tmp_path: Path) -> Path:
    path = tmp_path / "mcp-servers.yaml"
    path.write_text(
        f"""
servers:
  mock:
    enabled: true
    actors: [nexi, operator]
    tier: T0_READ
    tool_prefix: mock_
    command: {sys.executable}
    args: ["-m", "xnch_mcp.tests.fixtures.mock_mcp_server"]
    allow_tools: [ping_tool]
    deny_tools: [secret_tool]
"""
    )
    return path


@pytest.fixture
async def bridge_pool(mock_bridge_config: Path):
    pool = McpBridgePool(load_bridge_config(mock_bridge_config))
    await pool.start()
    set_bridge_pool(pool)
    yield pool
    await pool.stop()
    set_bridge_pool(None)


@pytest.mark.asyncio
async def test_bridge_registers_prefixed_tools(bridge_pool: McpBridgePool):
    names = {t.name for t in list_tools_for_actor("nexi")}
    assert "mock_ping_tool" in names
    assert "mock_secret_tool" not in names


@pytest.mark.asyncio
async def test_bridge_invoke_tool(bridge_pool: McpBridgePool):
    actor = ActorContext(actor_role="nexi", trace_id="t1", session_id="s1")
    result = await invoke_tool(
        app_state=object(),
        actor=actor,
        name="mock_ping_tool",
        arguments={"message": "hello"},
    )
    assert result == {"pong": True, "message": "hello"}


@pytest.mark.asyncio
async def test_bridge_server_status(bridge_pool: McpBridgePool):
    status = bridge_pool.server_status()
    assert len(status) == 1
    assert status[0]["server_id"] == "mock"
    assert status[0]["connected"] is True
    assert status[0]["tool_count"] == 1


@pytest.mark.asyncio
async def test_bridge_blocks_external_actor(bridge_pool: McpBridgePool):
    names = {t.name for t in list_tools_for_actor("external")}
    assert "mock_ping_tool" not in names
