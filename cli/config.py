"""CLI configuration from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CliConfig:
    base_url: str
    auth_secret: str
    auth_token: str
    actor: str
    nexi_url: str

    @classmethod
    def from_env(cls) -> "CliConfig":
        return cls(
            base_url=os.environ.get("XNCH_BASE_URL", "http://localhost:8001").rstrip("/"),
            auth_secret=os.environ.get("XNCH_AUTH_SECRET", ""),
            auth_token=os.environ.get("XNCH_AUTH_TOKEN", ""),
            actor=os.environ.get("XNCH_ACTOR", "operator"),
            nexi_url=os.environ.get("NEXI_BASE_URL", "http://localhost:8000").rstrip("/"),
        )
