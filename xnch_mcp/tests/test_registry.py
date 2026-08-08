"""Tests for MCP tool registry and auth tiers."""

import pytest

from xnch_mcp.auth import max_tier_for_role
from xnch_mcp.registry import get_registry, list_tools_for_actor
from xnch_mcp.tiers import ToolTier


def test_registry_loads_tools():
    tools = get_registry()
    names = {t.name for t in tools}
    assert "xnch_health" in names
    assert "xnch_memory_recall" in names
    assert "xnch_session_run" in names


def test_untrusted_gets_read_only():
    tools = list_tools_for_actor("external")
    assert all(t.tier == ToolTier.T0_READ for t in tools)
    assert "xnch_memory_store_note" not in {t.name for t in tools}


def test_opencode_gets_write_not_exec():
    tools = list_tools_for_actor("opencode")
    names = {t.name for t in tools}
    assert "xnch_memory_store_note" in names
    assert "xnch_session_run" not in names


def test_nexi_gets_exec():
    tools = list_tools_for_actor("nexi")
    assert "xnch_session_run" in {t.name for t in tools}


def test_max_tier_mapping():
    assert max_tier_for_role("external") == ToolTier.T0_READ
    assert max_tier_for_role("opencode") == ToolTier.T1_WRITE
    assert max_tier_for_role("nexi") == ToolTier.T2_EXEC
