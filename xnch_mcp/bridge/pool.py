"""Bridge pool — connect external MCP servers and expose bridged ToolDefs."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.types import Tool

from xnch_mcp.auth import max_tier_for_role
from xnch_mcp.bridge.client import McpServerClient
from xnch_mcp.bridge.config import BridgeConfig, ServerConfig, load_bridge_config
from xnch_mcp.context import ActorContext
from xnch_mcp.tool_def import ToolDef
from xnch_mcp.tiers import ToolTier

logger = logging.getLogger(__name__)

_bridge_pool: McpBridgePool | None = None


@dataclass(frozen=True)
class BridgedToolMeta:
    server_id: str
    original_name: str
    prefixed_name: str


class McpBridgePool:
    """Manage external MCP server connections and bridged tool definitions."""

    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self._clients: dict[str, McpServerClient] = {}
        self._tools: list[ToolDef] = []
        self._meta: dict[str, BridgedToolMeta] = {}
        self._started = False

    @classmethod
    def from_path(cls, path: Path) -> McpBridgePool:
        return cls(load_bridge_config(path))

    @property
    def started(self) -> bool:
        return self._started

    @property
    def has_enabled_servers(self) -> bool:
        return self.config.has_enabled_servers

    def get_meta(self, prefixed_name: str) -> BridgedToolMeta | None:
        return self._meta.get(prefixed_name)

    def all_tools(self) -> list[ToolDef]:
        return list(self._tools)

    def tools_for_actor(self, actor_role: str) -> list[ToolDef]:
        return [t for t in self._tools if _actor_may_use_tool(actor_role, t)]

    def server_status(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for server_id, cfg in self.config.servers.items():
            client = self._clients.get(server_id)
            tool_count = sum(
                1 for meta in self._meta.values() if meta.server_id == server_id
            )
            rows.append(
                {
                    "server_id": server_id,
                    "enabled": cfg.enabled,
                    "connected": client.connected if client else False,
                    "tool_prefix": cfg.tool_prefix,
                    "tool_count": tool_count,
                    "actors": sorted(cfg.actors),
                    "tier": cfg.tier.name,
                }
            )
        return rows

    async def start(self) -> None:
        if self._started:
            return

        for server_id, cfg in self.config.servers.items():
            if not cfg.enabled:
                continue
            client = McpServerClient(cfg)
            try:
                await client.start()
                self._clients[server_id] = client
                await self._register_server_tools(server_id, cfg, client)
            except Exception as exc:
                logger.error("MCP bridge failed to start %s: %s", server_id, exc)
                with contextlib.suppress(Exception):
                    await client.stop()

        self._started = True
        logger.info(
            "MCP bridge started (%d servers, %d tools)",
            len(self._clients),
            len(self._tools),
        )

    async def stop(self) -> None:
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()
        self._tools.clear()
        self._meta.clear()
        self._started = False

    async def invoke(
        self,
        prefixed_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        meta = self._meta.get(prefixed_name)
        if meta is None:
            raise ValueError(f"Unknown bridged tool: {prefixed_name}")

        client = self._clients.get(meta.server_id)
        if client is None or not client.connected:
            raise RuntimeError(f"MCP server not connected: {meta.server_id}")

        return await client.call_tool(meta.original_name, arguments)

    async def _register_server_tools(
        self,
        server_id: str,
        cfg: ServerConfig,
        client: McpServerClient,
    ) -> None:
        remote_tools = await client.list_tools()
        for remote in remote_tools:
            if not _tool_allowed(remote.name, cfg):
                continue
            prefixed = f"{cfg.tool_prefix}{remote.name}"
            if prefixed in self._meta:
                logger.warning(
                    "Skipping duplicate bridged tool %s from %s",
                    prefixed,
                    server_id,
                )
                continue

            meta = BridgedToolMeta(
                server_id=server_id,
                original_name=remote.name,
                prefixed_name=prefixed,
            )
            self._meta[prefixed] = meta
            self._tools.append(
                ToolDef(
                    name=prefixed,
                    description=_bridged_description(cfg, remote),
                    tier=cfg.tier,
                    input_schema=_tool_input_schema(remote),
                    handler=_make_handler(self, prefixed),
                    allowed_actors=cfg.actors,
                )
            )


def _tool_allowed(name: str, cfg: ServerConfig) -> bool:
    if name in cfg.deny_tools:
        return False
    if cfg.allow_tools is not None and name not in cfg.allow_tools:
        return False
    return True


def _tool_input_schema(tool: Tool) -> dict[str, Any]:
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    if isinstance(schema, dict):
        return schema
    return {"type": "object", "properties": {}}


def _bridged_description(cfg: ServerConfig, tool: Tool) -> str:
    if cfg.server_id == "agentmemory":
        prefix = "[agentmemory/curated] "
    else:
        prefix = f"[{cfg.server_id}] "
    return prefix + (tool.description or tool.name)


def _make_handler(pool: McpBridgePool, prefixed_name: str):
    async def _handler(
        _app: Any,
        _actor: ActorContext,
        arguments: dict[str, Any],
    ) -> Any:
        return await pool.invoke(prefixed_name, arguments)

    return _handler


def _actor_may_use_tool(actor_role: str, tool: ToolDef) -> bool:
    if tool.allowed_actors is not None and actor_role not in tool.allowed_actors:
        return False
    return tool.tier <= max_tier_for_role(actor_role)


def get_bridge_pool() -> McpBridgePool | None:
    return _bridge_pool


def set_bridge_pool(pool: McpBridgePool | None) -> None:
    global _bridge_pool
    _bridge_pool = pool
