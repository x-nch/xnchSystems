"""Tests for MCP bridge config loading."""

from pathlib import Path

import pytest

from xnch_mcp.bridge.config import load_bridge_config
from xnch_mcp.tiers import ToolTier


def test_load_bridge_config_missing_file(tmp_path: Path):
    cfg = load_bridge_config(tmp_path / "missing.yaml")
    assert cfg.servers == {}
    assert not cfg.has_enabled_servers


def test_load_bridge_config_parses_server(tmp_path: Path):
    path = tmp_path / "mcp-servers.yaml"
    path.write_text(
        """
servers:
  mock:
    enabled: true
    actors: [nexi]
    tier: T0_READ
    tool_prefix: mock_
    command: python
    args: ["-m", "xnch_mcp.tests.fixtures.mock_mcp_server"]
    allow_tools: [ping_tool]
    deny_tools: [secret_tool]
"""
    )
    cfg = load_bridge_config(path)
    assert "mock" in cfg.servers
    srv = cfg.servers["mock"]
    assert srv.command == "python"
    assert srv.args == ["-m", "xnch_mcp.tests.fixtures.mock_mcp_server"]
    assert srv.tool_prefix == "mock_"
    assert srv.tier == ToolTier.T0_READ
    assert srv.allow_tools == frozenset({"ping_tool"})
    assert srv.deny_tools == frozenset({"secret_tool"})


def test_load_bridge_config_invalid_tier(tmp_path: Path):
    path = tmp_path / "mcp-servers.yaml"
    path.write_text(
        """
servers:
  bad:
    command: echo
    tier: T9_INVALID
"""
    )
    with pytest.raises(ValueError, match="Unknown tier"):
        load_bridge_config(path)
