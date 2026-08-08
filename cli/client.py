"""HTTP client for xnch API endpoints."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import jwt

from xnch.routing.response_sanitize import strip_thinking

from .config import CliConfig

_STATE_PATH = Path("~/.xnch/cli_state.json").expanduser()


class XnchCliClient:
    def __init__(self, config: CliConfig | None = None) -> None:
        self.config = config or CliConfig.from_env()
        self._client = httpx.Client(base_url=self.config.base_url, timeout=120.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "XnchCliClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def auth_header(self) -> str:
        if self.config.auth_token:
            token = self.config.auth_token
            return token if token.startswith("Bearer ") else f"Bearer {token}"

        if self.config.auth_secret:
            payload = {
                "sub": self.config.actor,
                "iss": "xnch",
                "exp": int(time.time()) + 3600,
            }
            token = jwt.encode(payload, self.config.auth_secret, algorithm="HS256")
            return f"Bearer {token}"

        return f"actor:{self.config.actor}"

    def health(self) -> dict[str, Any]:
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def nexi_health(self) -> dict[str, Any]:
        with httpx.Client(base_url=self.config.nexi_url, timeout=10.0) as client:
            resp = client.get("/health")
            resp.raise_for_status()
            return resp.json()

    def system_state(self) -> dict[str, Any]:
        resp = self._client.get("/system/state")
        resp.raise_for_status()
        return resp.json()

    def session_init(self, raw_input: str, *, priority: str = "NORMAL") -> dict[str, Any]:
        resp = self._client.post(
            "/session/init",
            json={
                "auth_token": self.auth_header(),
                "raw_input": raw_input,
                "input_type": "TEXT",
                "priority": priority,
                "source_system": "xnch-cli",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def chat(self, message: str, *, session_id: str | None = None, actor_role: str | None = None) -> dict[str, Any]:
        sid = session_id or self._load_session_id()
        resp = self._client.post(
            "/nexi/chat",
            json={
                "session_id": sid,
                "message": message,
                "actor_role": actor_role or self.config.actor,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "response" in data:
            data["response"] = strip_thinking(data["response"])
        self._save_session_id(data.get("session_id", sid))
        return data

    def chat_stream(self, message: str, *, session_id: str | None = None, actor_role: str | None = None) -> str:
        sid = session_id or self._load_session_id()
        full_text = ""

        with self._client.stream(
            "POST",
            "/nexi/chat/stream",
            json={
                "session_id": sid,
                "message": message,
                "actor_role": actor_role or self.config.actor,
            },
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ")
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "error" in chunk:
                    raise RuntimeError(chunk["error"])
                delta = chunk.get("content", "")
                if delta:
                    print(delta, end="", flush=True)
                    full_text += delta

        print()
        self._save_session_id(sid)
        return full_text

    def memory_recall(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        resp = self._client.post("/nexi/memory/recall", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        return resp.json()

    def memory_surface(self) -> list[dict[str, Any]]:
        resp = self._client.get("/nexi/memory/surface")
        resp.raise_for_status()
        return resp.json()

    def mcp_headers(self, *, actor_role: str | None = None) -> dict[str, str]:
        return {"X-Actor-Role": actor_role or self.config.actor}

    def mcp_servers(self, *, actor_role: str | None = None) -> dict[str, Any]:
        resp = self._client.get("/mcp/servers", headers=self.mcp_headers(actor_role=actor_role))
        resp.raise_for_status()
        return resp.json()

    def mcp_tools(self, *, actor_role: str | None = None) -> dict[str, Any]:
        resp = self._client.get("/mcp/tools", headers=self.mcp_headers(actor_role=actor_role))
        resp.raise_for_status()
        return resp.json()

    def mcp_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/mcp/call",
            json={"name": name, "arguments": arguments or {}},
            headers=self.mcp_headers(actor_role=actor_role),
        )
        resp.raise_for_status()
        return resp.json()

    def mint_token(self, *, actor: str | None = None, ttl_s: int = 3600) -> str:
        if not self.config.auth_secret:
            raise RuntimeError("XNCH_AUTH_SECRET is required to mint JWT tokens")
        payload = {
            "sub": actor or self.config.actor,
            "iss": "xnch",
            "exp": int(time.time()) + ttl_s,
        }
        return jwt.encode(payload, self.config.auth_secret, algorithm="HS256")

    def new_session(self) -> str:
        """Generate a fresh session id and persist it as the CLI default."""
        session_id = f"cli-{uuid4().hex[:12]}"
        self._save_session_id(session_id)
        return session_id

    def clear_session(self) -> str:
        """Reset the stored session (server has no clear endpoint yet)."""
        return self.new_session()

    def _load_session_id(self) -> str:
        if _STATE_PATH.exists():
            try:
                data = json.loads(_STATE_PATH.read_text())
                if sid := data.get("session_id"):
                    return sid
            except (json.JSONDecodeError, OSError):
                pass
        return f"cli-{uuid4().hex[:12]}"

    def _save_session_id(self, session_id: str) -> None:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps({"session_id": session_id}, indent=2))
