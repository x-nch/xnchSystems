"""FastAPI application for the unified agent gateway."""

from __future__ import annotations

import json
import logging
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from .adapters.base import AgentRequest
from .config import settings
from .message_adapter import messages_to_prompt
from .models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ModelInfo,
    ModelsResponse,
    UsageInfo,
)
from .router import MODEL_CATALOG, get_adapter, route_model

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agent Gateway",
    description="OpenAI-compatible API for Claude Code, OpenCode, and Cursor Agent",
    version="0.1.0",
)


def _verify_api_key(authorization: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    assert settings.api_key is not None
    if not secrets.compare_digest(token.encode(), settings.api_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")


def _resolve_cwd() -> Path | None:
    return settings.cwd.expanduser() if settings.cwd else None


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "backends": sorted({backend for _, backend, _ in MODEL_CATALOG}),
        "models": [model_id for model_id, _, _ in MODEL_CATALOG],
        "default_backend": settings.default_backend,
    }


@app.get("/v1/models")
async def list_models(_: None = Depends(_verify_api_key)) -> ModelsResponse:
    data = [
        ModelInfo(id=model_id, owned_by=owner, backend=backend)
        for model_id, backend, owner in MODEL_CATALOG
    ]
    return ModelsResponse(data=data)


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionRequest,
    _: None = Depends(_verify_api_key),
):
    try:
        routed = route_model(body.model)
        adapter = get_adapter(routed.backend)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    prompt, system_prompt = messages_to_prompt(body.messages)
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="No user prompt found in messages")
    if len(prompt) > settings.max_prompt_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Prompt too long: {len(prompt)} chars (max {settings.max_prompt_chars})",
        )

    request = AgentRequest(
        prompt=prompt,
        system_prompt=system_prompt,
        model=routed.model,
        cwd=_resolve_cwd(),
        stream=body.stream,
    )

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if body.stream:
        return StreamingResponse(
            _stream_openai_sse(
                adapter=adapter,
                request=request,
                completion_id=completion_id,
                created=created,
                model_id=routed.model_id,
            ),
            media_type="text/event-stream",
        )

    try:
        result = await adapter.run(request, timeout_seconds=settings.timeout_seconds)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if result.is_error:
        raise HTTPException(status_code=502, detail=result.content)

    usage = UsageInfo(
        prompt_tokens=result.usage.get("prompt_tokens", 0),
        completion_tokens=result.usage.get("completion_tokens", 0),
        total_tokens=result.usage.get("total_tokens", 0),
    )
    response = ChatCompletionResponse(
        id=completion_id,
        created=created,
        model=routed.model_id,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=result.content),
                finish_reason=result.finish_reason,
            )
        ],
        usage=usage,
    )
    payload = response.model_dump()
    if result.session_id:
        payload["session_id"] = result.session_id
    return JSONResponse(content=payload)


async def _stream_openai_sse(
    *,
    adapter,
    request: AgentRequest,
    completion_id: str,
    created: int,
    model_id: str,
) -> AsyncIterator[str]:
    role_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_id,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(role_chunk)}\n\n"

    try:
        async for chunk in adapter.stream(request, timeout_seconds=settings.timeout_seconds):
            if chunk.delta:
                payload = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_id,
                    "choices": [{"index": 0, "delta": {"content": chunk.delta}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(payload)}\n\n"

            if chunk.finish_reason:
                usage = chunk.usage or {}
                done_payload = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_id,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": chunk.finish_reason}],
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                }
                if chunk.session_id:
                    done_payload["session_id"] = chunk.session_id
                yield f"data: {json.dumps(done_payload)}\n\n"
    except TimeoutError as exc:
        error_payload = {"error": {"message": str(exc), "type": "timeout_error"}}
        yield f"data: {json.dumps(error_payload)}\n\n"
    except RuntimeError as exc:
        error_payload = {"error": {"message": str(exc), "type": "agent_error"}}
        yield f"data: {json.dumps(error_payload)}\n\n"

    yield "data: [DONE]\n\n"


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "agent_gateway.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
