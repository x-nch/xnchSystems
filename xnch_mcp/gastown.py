"""Gastown client — spawn/status for Mac workstream manager."""

from __future__ import annotations

from typing import Any

import httpx


class GastownError(Exception):
    """Raised when Gas Town returns a non-2xx response or transport fails."""


SPAWN_PATH = "/api/workstreams"
STATUS_PATH = "/api/workstreams"


class GastownClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 15.0,
        transport: httpx.AsyncTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout, transport=self._transport
        ) as client:
            try:
                resp = await client.request(method, path, headers=headers, **kwargs)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise GastownError(
                    f"Gas Town {exc.response.status_code}: {exc.response.text}"
                ) from exc
            return resp.json()

    async def spawn(
        self,
        title: str,
        goal: str,
        workspace_hint: str | None = None,
        agent_hint: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"title": title, "goal": goal}
        if workspace_hint is not None:
            body["workspace_hint"] = workspace_hint
        if agent_hint is not None:
            body["agent_hint"] = agent_hint
        return await self._request("POST", SPAWN_PATH, json=body)

    async def status(self, workstream_id: str | None = None) -> dict[str, Any]:
        path = f"{STATUS_PATH}/{workstream_id}" if workstream_id else STATUS_PATH
        return await self._request("GET", path)
