"""HTTP client for fs-read-agent on remote hosts."""

from __future__ import annotations

from typing import Any

import httpx


class FsRemoteClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Internal-Token": token} if token else {}
        self._timeout = timeout

    def _params(self, **kwargs: Any) -> dict[str, Any]:
        return {k: v for k, v in kwargs.items() if v is not None}

    async def list_dir(
        self,
        path: str,
        *,
        recursive: bool = False,
        max_entries: int = 1000,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.get(
                "/list",
                params=self._params(path=path, recursive=recursive, max_entries=max_entries),
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def read(
        self,
        path: str,
        *,
        offset: int = 0,
        max_bytes: int = 2_097_152,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.get(
                "/read",
                params=self._params(path=path, offset=offset, max_bytes=max_bytes),
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def stat(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.get("/stat", params={"path": path}, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def exists(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.get("/exists", params={"path": path}, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def glob(self, pattern: str, *, max_results: int = 200) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.get(
                "/glob",
                params={"pattern": pattern, "max_results": max_results},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.get("/health", headers=self._headers)
            resp.raise_for_status()
            return resp.json()
