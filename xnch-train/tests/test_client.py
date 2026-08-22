"""ModelClient protocol implementations — vLLM HTTP client + deterministic fake."""
import json
from typing import Any

import httpx
import pytest

from xnch_train.evalharness.client import FakeModelClient, VllmOpenAIClient
from xnch_train.evalharness.qwen3xml import parse_tool_calls


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
    assert captured["url"].endswith("/v1/chat/completions")
    assert '"model": "ornith"' in body or '"model":"ornith"' in body
    payload = json.loads(body)
    assert payload["max_tokens"] == 32
    assert payload["messages"] == [{"role": "user", "content": "hello"}]
    await client.aclose()


async def test_vllm_reassembles_dict_arguments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {
                "tool_calls": [{"function": {
                    "name": "deploy",
                    "arguments": {"env": "prod"},
                }}],
            }}],
        })

    client = VllmOpenAIClient(base_url="http://vllm.test", model="ornith")
    client._client = httpx.AsyncClient(  # type: ignore[assignment]
        base_url="http://vllm.test", transport=httpx.MockTransport(handler)
    )
    reply = await client.complete("go", max_tokens=16)
    calls = parse_tool_calls(reply.text)
    assert calls == [{"name": "deploy", "arguments": {"env": "prod"}}]
    await client.aclose()
