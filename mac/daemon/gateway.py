"""HTTP client for gate7 xnch and node-b media-gateway."""

from __future__ import annotations

import httpx

from .config import DaemonConfig


class GatewayClient:
    def __init__(self, config: DaemonConfig, transport: httpx.Transport | None = None) -> None:
        self.config = config
        self._transport = transport
        self._http = httpx.Client(base_url=config.base_url, timeout=120.0, transport=transport)

    def close(self) -> None:
        self._http.close()

    def voice_chat(
        self,
        wav_bytes: bytes,
        *,
        session_id: str | None = None,
        actor_role: str | None = None,
        return_audio: bool = True,
    ) -> dict:
        resp = self._http.post(
            "/nexi/voice/chat",
            files={"audio": ("audio.wav", wav_bytes, "audio/wav")},
            data={
                "session_id": session_id or "cc-default",
                "actor_role": actor_role or self.config.actor,
                "return_audio": "true" if return_audio else "false",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        resp = self._http.get("/health")
        resp.raise_for_status()
        return resp.json()

    def nexi_health(self) -> dict:
        with httpx.Client(base_url=self.config.nexi_url, timeout=10.0, transport=self._transport) as client:
            resp = client.get("/health")
            resp.raise_for_status()
            return resp.json()

    def media_health(self) -> dict:
        with httpx.Client(base_url=self.config.media_url, timeout=10.0, transport=self._transport) as client:
            resp = client.get("/health")
            resp.raise_for_status()
            return resp.json()
