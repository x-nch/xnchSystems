"""Gateway configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_GATEWAY_",
        env_file=".env",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8100
    api_key: str | None = None
    default_backend: str = "claude-code"
    cwd: Path | None = None
    timeout_seconds: int = 600
    max_prompt_chars: int = 100_000

    claude_cli: str = "claude"
    opencode_cli: str = "opencode"
    cursor_cli: str = "agent"

    opencode_auto_approve: bool = True


settings = Settings()
