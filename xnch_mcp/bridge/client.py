"""Long-lived stdio MCP client for one external server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, Tool

from xnch_mcp.bridge.config import ServerConfig
from xnch_mcp.bridge.result import serialize_call_result

logger = logging.getLogger(__name__)


class McpServerClient:
    """Maintain one stdio MCP subprocess and session in a supervisor task."""

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._session: ClientSession | None = None
        self._connected = False
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._supervisor: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._connected

    async def start(self) -> None:
        if self._supervisor is not None:
            await self._ready.wait()
            return

        self._supervisor = asyncio.create_task(
            self._supervise(),
            name=f"mcp-bridge-{self.config.server_id}",
        )
        await self._ready.wait()
        if not self._connected:
            raise RuntimeError(f"MCP bridge failed to connect: {self.config.server_id}")

    async def stop(self) -> None:
        if self._supervisor is None:
            return
        self._stop.set()
        try:
            with contextlib.suppress(Exception):
                await self._supervisor
        finally:
            self._supervisor = None
            self._session = None
            self._connected = False
            self._ready.clear()
            self._stop.clear()
            logger.info("MCP bridge disconnected: %s", self.config.server_id)

    async def _supervise(self) -> None:
        params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env or None,
        )
        try:
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    self._session = session
                    await session.initialize()
                    self._connected = True
                    self._ready.set()
                    logger.info("MCP bridge connected: %s", self.config.server_id)
                    await self._stop.wait()
        except Exception as exc:
            logger.error("MCP bridge supervisor error (%s): %s", self.config.server_id, exc)
            self._connected = False
            self._ready.set()
            raise
        finally:
            self._connected = False

    async def list_tools(self) -> list[Tool]:
        async with self._lock:
            if self._session is None:
                raise RuntimeError(f"MCP client not connected: {self.config.server_id}")
            result = await self._session.list_tools()
            return list(result.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        async with self._lock:
            if self._session is None:
                raise RuntimeError(f"MCP client not connected: {self.config.server_id}")
            result: CallToolResult = await self._session.call_tool(name, arguments)
            return serialize_call_result(result)
