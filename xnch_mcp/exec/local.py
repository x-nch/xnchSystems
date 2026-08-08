"""Local subprocess execution (no shell)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from xnch_mcp.exec.policy import ExecDenied, ExecPolicy


class LocalExecBackend:
    def __init__(self, policy: ExecPolicy, host: str) -> None:
        self._policy = policy
        self._host = host

    async def run(
        self,
        command: str,
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        argv, work_dir = self._policy.validate(self._host, command, cwd=cwd)

        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._policy.timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(
                f"command timed out after {self._policy.timeout_seconds}s"
            ) from None

        cap = self._policy.max_output_bytes
        stdout = (stdout_b or b"")[:cap].decode("utf-8", errors="replace")
        stderr = (stderr_b or b"")[:cap].decode("utf-8", errors="replace")
        truncated = len(stdout_b or b"") > cap or len(stderr_b or b"") > cap

        return {
            "host": self._host,
            "command": command,
            "argv": argv,
            "cwd": str(work_dir),
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": truncated,
        }
