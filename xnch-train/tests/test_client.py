"""ModelClient protocol implementations — vLLM HTTP client + deterministic fake."""
from typing import Any

import httpx
import pytest

from xnch_train.evalharness.client import FakeModelClient, VllmOpenAIClient


async def test_fake_cycles_replies() -> None:
    fake = FakeModelClient(["a", "b"])
    r1 = await fake.complete("p1")
    r2 = await fake.complete("p2")
    r3 = await fake.complete("p3")
    assert (r1.text, r2.text, r3.text) == ("a", "b", "a")
    assert r1.latency_ms == 10.0


async def test_vllm_client_posts_openai_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
        })

    transport = httpx.MockTransport(handler)
    client = VllmOpenAIClient(base_url="http://vllm.test", model="ornith")
    client._client = httpx.AsyncClient(  # type: ignore[assignment]
        base_url="http://vllm.test", transport=transport
    )
    reply = await client.complete("hello", max_tokens=32)
    assert reply.text == "ok"
    assert reply.latency_ms >= 0
    body = captured["body"].decode()
    assert '"model": "ornith"' in body or '"model":"ornith"' in body
    assert "hello" in body
    await client.aclose()
