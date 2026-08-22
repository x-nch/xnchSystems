"""Shared adapter types and subprocess helpers."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentRequest:
    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    session_id: str | None = None
    cwd: Path | None = None
    stream: bool = False


@dataclass
class AgentResult:
    content: str
    session_id: str | None = None
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    is_error: bool = False


@dataclass
class AgentStreamChunk:
    delta: str
    finish_reason: str | None = None
    session_id: str | None = None
    usage: dict[str, int] | None = None


class AgentAdapter(ABC):
    backend: str

    @abstractmethod
    def build_command(self, request: AgentRequest) -> list[str]:
        """Build the CLI invocation."""

    @abstractmethod
    def parse_result_line(self, line: str, accumulated: str) -> tuple[str, AgentResult | None]:
        """Parse one JSONL line; return updated accumulated text and optional final result."""

    @abstractmethod
    def parse_stream_line(self, line: str) -> AgentStreamChunk | None:
        """Parse one JSONL line into a stream chunk."""

    async def run(self, request: AgentRequest, timeout_seconds: int) -> AgentResult:
        cmd = self.build_command(request)
        cwd = str(request.cwd) if request.cwd else None
        logger.info("Running %s: %s", self.backend, " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"{self.backend} timed out after {timeout_seconds}s") from None

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(err or f"{self.backend} exited with code {proc.returncode}")

        accumulated = ""
        result: AgentResult | None = None
        for raw_line in stdout.decode("utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            accumulated, maybe_result = self.parse_result_line(line, accumulated)
            if maybe_result is not None:
                result = maybe_result

        if result is not None:
            return result

        if accumulated:
            return AgentResult(content=accumulated)

        text = stdout.decode("utf-8", errors="replace").strip()
        if text:
            return AgentResult(content=text)

        raise RuntimeError(f"{self.backend} returned no output")

    async def stream(self, request: AgentRequest, timeout_seconds: int) -> AsyncIterator[AgentStreamChunk]:
        cmd = self.build_command(request)
        cwd = str(request.cwd) if request.cwd else None
        logger.info("Streaming %s: %s", self.backend, " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stderr_buf = bytearray()

        async def _drain_stderr() -> None:
            assert proc.stderr is not None
            while True:
                chunk = await proc.stderr.read(65536)
                if not chunk:
                    break
                stderr_buf.extend(chunk)

        stderr_task = asyncio.create_task(_drain_stderr())
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds

        def _remaining() -> float:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(f"{self.backend} stream timed out after {timeout_seconds}s")
            return remaining

        try:
            assert proc.stdout is not None
            while True:
                try:
                    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=_remaining())
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise TimeoutError(f"{self.backend} stream timed out after {timeout_seconds}s") from None

                if not raw:
                    break

                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                chunk = self.parse_stream_line(line)
                if chunk is not None:
                    yield chunk

            await proc.wait()
            await stderr_task
            if proc.returncode not in (0, None):
                err = stderr_buf.decode("utf-8", errors="replace").strip()
                raise RuntimeError(err or f"{self.backend} exited with code {proc.returncode}")
        finally:
            stderr_task.cancel()
            if proc.returncode is None:
                proc.kill()
                await proc.wait()


def parse_json_line(line: str) -> dict[str, object] | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
