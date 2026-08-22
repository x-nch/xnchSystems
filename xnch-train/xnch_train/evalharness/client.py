"""Inference clients for the eval harness (OpenAI-compatible endpoints)."""
import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from .qwen3xml import parse_tool_calls  # noqa: F401 — re-export convenience


class ModelReply(BaseModel):
    text: str
    latency_ms: float


class ModelClient(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int = 512) -> ModelReply: ...


class VllmOpenAIClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
        timeout_s: float = 120.0,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, prompt: str, *, max_tokens: int = 512) -> ModelReply:
        started = time.perf_counter()
        resp = await self._client.post(
            "/v1/chat/completions",
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - started) * 1000.0
        choice = resp.json()["choices"][0]
        message = choice.get("message", {})
        text = message.get("content") or ""
        if not text and message.get("tool_calls"):
            text = "".join(
                f'<tool_call>{{"name": "{tc["function"]["name"]}", '
                f'"arguments": {tc["function"]["arguments"]}}}</tool_call>'
                for tc in message["tool_calls"]
            )
        return ModelReply(text=text, latency_ms=latency_ms)


class FakeModelClient:
    def __init__(self, replies: list[str], latency_ms: float = 10.0) -> None:
        self._replies = replies
        self._latency_ms = latency_ms
        self._index = 0

    async def complete(self, prompt: str, *, max_tokens: int = 512) -> ModelReply:
        reply = self._replies[self._index % len(self._replies)]
        self._index += 1
        return ModelReply(text=reply, latency_ms=self._latency_ms)
