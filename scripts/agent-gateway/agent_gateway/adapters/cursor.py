"""Cursor Agent CLI adapter."""

from __future__ import annotations

from ..config import settings
from .base import AgentAdapter, AgentRequest, AgentResult, AgentStreamChunk, estimate_tokens, parse_json_line


class CursorAgentAdapter(AgentAdapter):
    backend = "cursor-agent"

    def build_command(self, request: AgentRequest) -> list[str]:
        cmd = [
            settings.cursor_cli,
            "-p",
            request.prompt,
            "--output-format",
            "json" if not request.stream else "stream-json",
        ]
        if request.model:
            cmd.extend(["--model", request.model])
        if request.cwd:
            cmd.extend(["--workspace", str(request.cwd)])
        return cmd

    def parse_result_line(self, line: str, accumulated: str) -> tuple[str, AgentResult | None]:
        payload = parse_json_line(line)
        if payload is None:
            return accumulated + line, None

        event_type = payload.get("type")
        if event_type == "assistant":
            text = _extract_text(payload)
            if text:
                accumulated += text
            return accumulated, None

        if event_type == "result":
            result_text = str(payload.get("result") or accumulated)
            usage = _usage_from_payload(payload)
            return result_text, AgentResult(
                content=result_text,
                session_id=_session_id(payload),
                finish_reason="stop" if not payload.get("is_error") else "error",
                usage=usage,
                is_error=bool(payload.get("is_error")),
            )

        return accumulated, None

    def parse_stream_line(self, line: str) -> AgentStreamChunk | None:
        payload = parse_json_line(line)
        if payload is None:
            return None

        event_type = payload.get("type")
        if event_type in ("assistant", "content"):
            text = _extract_text(payload)
            if text:
                return AgentStreamChunk(delta=text)
            return None

        if event_type == "result":
            usage = _usage_from_payload(payload)
            return AgentStreamChunk(
                delta="",
                finish_reason="stop" if not payload.get("is_error") else "error",
                session_id=_session_id(payload),
                usage=usage,
            )

        subtype = payload.get("subtype")
        if subtype == "delta":
            text = str(payload.get("text") or payload.get("delta") or "")
            if text:
                return AgentStreamChunk(delta=text)

        return None


def _extract_text(payload: dict[str, object]) -> str:
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)

    text = payload.get("text")
    if isinstance(text, str):
        return text
    return ""


def _session_id(payload: dict[str, object]) -> str | None:
    session_id = payload.get("session_id")
    return session_id if isinstance(session_id, str) else None


def _usage_from_payload(payload: dict[str, object]) -> dict[str, int]:
    usage_obj = payload.get("usage")
    if not isinstance(usage_obj, dict):
        result_text = str(payload.get("result") or "")
        tokens = estimate_tokens(result_text)
        return {"prompt_tokens": tokens, "completion_tokens": tokens, "total_tokens": tokens * 2}

    input_tokens = int(usage_obj.get("inputTokens") or usage_obj.get("input_tokens") or 0)
    output_tokens = int(usage_obj.get("outputTokens") or usage_obj.get("output_tokens") or 0)
    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
