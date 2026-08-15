"""Daemon configuration from environment variables."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


def _device(raw: str) -> int | str | None:
    raw = raw.strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw


@dataclass(frozen=True)
class DaemonConfig:
    base_url: str
    auth_secret: str
    auth_token: str
    actor: str
    nexi_url: str
    media_url: str
    sample_rate: int
    input_device: int | str | None
    output_device: int | str | None
    ws_host: str
    ws_port: int
    http_port: int

    @classmethod
    def from_env(cls) -> "DaemonConfig":
        return cls(
            base_url=os.environ.get("XNCH_BASE_URL", "http://192.168.1.10:8001").rstrip("/"),
            auth_secret=os.environ.get("XNCH_AUTH_SECRET", ""),
            auth_token=os.environ.get("XNCH_AUTH_TOKEN", ""),
            actor=os.environ.get("XNCH_ACTOR", "operator"),
            nexi_url=os.environ.get("NEXI_BASE_URL", "http://192.168.1.9:8001").rstrip("/"),
            media_url=os.environ.get("MEDIA_GATEWAY_URL", "http://192.168.1.9:8090").rstrip("/"),
            sample_rate=int(os.environ.get("XNCH_VOICE_SAMPLE_RATE", "16000")),
            input_device=_device(os.environ.get("XNCH_VOICE_INPUT_DEVICE", "")),
            output_device=_device(os.environ.get("XNCH_VOICE_OUTPUT_DEVICE", "")),
            ws_host=os.environ.get("XNCH_CC_WS_HOST", "127.0.0.1"),
            ws_port=int(os.environ.get("XNCH_CC_WS_PORT", "9001")),
            http_port=int(os.environ.get("XNCH_CC_HTTP_PORT", "9002")),
        )

    def auth_header(self) -> str:
        if self.auth_token:
            token = self.auth_token
            return token if token.startswith("Bearer ") else f"Bearer {token}"
        if self.auth_secret:
            import jwt
            payload = {"sub": self.actor, "iss": "xnch", "exp": int(time.time()) + 3600}
            return f"Bearer {jwt.encode(payload, self.auth_secret, algorithm='HS256')}"
        return f"actor:{self.actor}"
