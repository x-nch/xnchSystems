"""OpenCode CLI adapter."""

from __future__ import annotations

from ..config import settings
from .base import AgentAdapter, AgentRequest, AgentResult, AgentStreamChunk, estimate_tokens, parse_json_line


class OpenCodeAdapter(AgentAdapter):
    backend = "opencode"

    def build_command(self, request: AgentRequest) -> list[str]:
        cmd = [
            settings.opencode_cli,
            "run",
            request.prompt,
            "--format",
            "json",
        ]
        if settings.opencode_auto_approve:
            cmd.append("--auto")
        if request.model:
            cmd.extend(["--agent", request.model])
        if request.session_id:
            cmd.extend(["--session", request.session_id])
        if request.cwd:
            cmd.extend(["--dir", str(request.cwd)])
        return cmd

    def parse_result_line(self, line: str, accumulated: str) -> tuple[str, AgentResult | None]:
        payload = parse_json_line(line)
        if payload is None:
            return accumulated + line, None

        event_type = payload.get("type")
        if event_type == "text":
            text = _text_from_part(payload)
            if text:
                accumulated += text
            return accumulated, None

        if event_type == "step_finish":
            part = payload.get("part")
            reason = None
            if isinstance(part, dict):
                reason = part.get("reason")
            if reason not in (None, "stop", "unknown"):
                return accumulated, None

            usage = _usage_from_step_finish(part if isinstance(part, dict) else {})
            return accumulated, AgentResult(
                content=accumulated,
                session_id=_session_id(payload),
                usage=usage,
            )

        if event_type == "error":
            message = str(payload.get("error") or payload.get("message") or "OpenCode error")
            return accumulated, AgentResult(
                content=message,
                session_id=_session_id(payload),
                finish_reason="error",
                is_error=True,
            )

        return accumulated, None

    def parse_stream_line(self, line: str) -> AgentStreamChunk | None:
        payload = parse_json_line(line)
        if payload is None:
            return None

        event_type = payload.get("type")
        if event_type == "text":
            text = _text_from_part(payload)
            if text:
                return AgentStreamChunk(delta=text)
            return None

        if event_type == "step_finish":
            part = payload.get("part")
            reason = None
            if isinstance(part, dict):
                reason = part.get("reason")
            if reason not in (None, "stop", "unknown"):
                return None
            usage = _usage_from_step_finish(part if isinstance(part, dict) else {})
            return AgentStreamChunk(
                delta="",
                finish_reason="stop",
                session_id=_session_id(payload),
                usage=usage,
            )

        if event_type == "error":
            message = str(payload.get("error") or payload.get("message") or "OpenCode error")
            return AgentStreamChunk(delta=message, finish_reason="error")

        return None


def _text_from_part(payload: dict[str, object]) -> str:
    part = payload.get("part")
    if not isinstance(part, dict):
        return ""
    text = part.get("text")
    return text if isinstance(text, str) else ""


def _session_id(payload: dict[str, object]) -> str | None:
    session_id = payload.get("sessionID") or payload.get("session_id")
    return session_id if isinstance(session_id, str) else None


def _usage_from_step_finish(part: dict[str, object]) -> dict[str, int]:
    tokens = part.get("tokens")
    if not isinstance(tokens, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    input_tokens = int(tokens.get("input") or 0)
    output_tokens = int(tokens.get("output") or 0)
    if input_tokens == 0 and output_tokens == 0:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
