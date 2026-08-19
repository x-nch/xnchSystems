"""Async adapter wrapping the synchronous XnchCliClient for Textual workers."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import httpx

from cli.client import XnchCliClient
from cli.config import CliConfig


class AsyncXnchClient:
    """Async wrapper over XnchCliClient for Textual workers.

    Uses asyncio.to_thread for synchronous httpx calls,
    and httpx.AsyncClient for SSE streaming.
    """

    def __init__(self, config: CliConfig | None = None) -> None:
        self.config = config or CliConfig.from_env()
        self._sync = XnchCliClient(self.config)
        self._stream_client = httpx.AsyncClient(
            base_url=self.config.nexi_url, timeout=120.0
        )

    async def close(self) -> None:
        self._sync.close()
        await self._stream_client.aclose()

    # ── Health ──────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.health)

    async def nexi_health(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.nexi_health)

    async def system_state(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.system_state)

    # ── Chat ────────────────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        *,
        session_id: str | None = None,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.chat, message, session_id=session_id, actor_role=actor_role
        )

    async def chat_stream(
        self,
        message: str,
        *,
        session_id: str | None = None,
        actor_role: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """Stream chat via SSE, calling on_token for each content delta."""
        sid = session_id or await asyncio.to_thread(self._sync._load_session_id)
        full_text = ""

        async with self._stream_client.stream(
            "POST",
            "/nexi/chat/stream",
            json={
                "session_id": sid,
                "message": message,
                "actor_role": actor_role or self.config.actor,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ")
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "error" in chunk:
                    raise RuntimeError(chunk["error"])
                delta = chunk.get("content", "")
                if delta:
                    full_text += delta
                    if on_token:
                        on_token(delta)

        await asyncio.to_thread(self._sync._save_session_id, sid)
        return full_text

    # ── Memory ──────────────────────────────────────────────────────

    async def memory_recall(
        self, query: str, *, top_k: int = 5
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sync.memory_recall, query, top_k=top_k)

    async def memory_surface(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sync.memory_surface)

    # ── Session ─────────────────────────────────────────────────────

    async def new_session(self) -> str:
        return await asyncio.to_thread(self._sync.new_session)

    async def clear_session(self) -> str:
        return await asyncio.to_thread(self._sync.clear_session)

    def current_session_id(self) -> str:
        return self._sync._load_session_id()

    # ── MCP ─────────────────────────────────────────────────────────

    async def mcp_tools(
        self, *, actor_role: str | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.mcp_tools, actor_role=actor_role)

    async def mcp_servers(
        self, *, actor_role: str | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.mcp_servers, actor_role=actor_role)

    async def mcp_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.mcp_call, name, arguments, actor_role=actor_role
        )

    # ── Voice ──────────────────────────────────────────────────────

    async def voice_transcribe(self, wav_bytes: bytes) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.voice_transcribe, wav_bytes)

    async def voice_speak(self, text: str) -> bytes:
        return await asyncio.to_thread(self._sync.voice_speak, text)

    async def voice_chat(
        self,
        wav_bytes: bytes,
        *,
        session_id: str | None = None,
        actor_role: str | None = None,
        return_audio: bool = True,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.voice_chat,
            wav_bytes,
            session_id=session_id,
            actor_role=actor_role,
            return_audio=return_audio,
        )

    # ── Token ───────────────────────────────────────────────────────

    async def mint_token(
        self, *, actor: str | None = None, ttl_s: int = 3600
    ) -> str:
        return await asyncio.to_thread(
            self._sync.mint_token, actor=actor, ttl_s=ttl_s
        )
