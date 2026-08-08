"""MCP bridge — federate external MCP servers into xnch tool registry."""

from xnch_mcp.bridge.config import BridgeConfig, ServerConfig, load_bridge_config
from xnch_mcp.bridge.pool import McpBridgePool, get_bridge_pool, set_bridge_pool

__all__ = [
    "BridgeConfig",
    "McpBridgePool",
    "ServerConfig",
    "get_bridge_pool",
    "load_bridge_config",
    "set_bridge_pool",
]
