"""HTTP client for exec-agent on remote hosts."""

from __future__ import annotations

from typing import Any

import httpx


class ExecRemoteClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Internal-Token": token} if token else {}
        self._timeout = timeout

    async def run(self, command: str, *, cwd: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"command": command}
        if cwd:
            payload["cwd"] = cwd
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.post("/run", json=payload, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.get("/health", headers=self._headers)
            resp.raise_for_status()
            return resp.json()
