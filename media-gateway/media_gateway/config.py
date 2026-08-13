"""Gateway configuration — env-driven, fail-closed.

Env vars (see media.env on Node B):
  MEDIA_GATEWAY_TOKEN            bearer token required on all /media/* routes
  MEDIA_GATEWAY_BIND             bind address (private interface, not 0.0.0.0)
  MEDIA_GATEWAY_PORT             default 8090
  MEDIA_GATEWAY_INBOX_DIR        upload staging dir
  MEDIA_GATEWAY_OUTBOX_DIR       results dir
  MEDIA_GATEWAY_MAX_UPLOAD_MB    per-file upload cap
  MEDIA_GATEWAY_ALLOWED_EXTENSIONS  comma-separated allowlist
  MEDIA_GATEWAY_COMFY_URL / _INPUT_DIR / _OUTPUT_DIR   ComfyUI endpoint + dirs
  MEDIA_GATEWAY_WORKFLOWS_DIR    ComfyUI API-graph templates
  MEDIA_GATEWAY_LITELLM_URL / _KEY  qwen-vl vLLM endpoint (direct on Node B) + optional key
  MEDIA_GATEWAY_QWEN_MODEL / _MAX_TOKENS  qwen-vl model name + token cap
  LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST   observability
"""
import logging
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
}


def _expanded(path: Path) -> Path:
    return path.expanduser().resolve()


def _default_workflows_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "workflows"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        populate_by_name=True,
        extra="ignore",
    )

    token: str = Field(default="", alias="MEDIA_GATEWAY_TOKEN")
    bind_host: str = Field(default="127.0.0.1", alias="MEDIA_GATEWAY_BIND")
    port: int = Field(default=8090, alias="MEDIA_GATEWAY_PORT")
    inbox_dir: Path = Field(
        default=Path("~/media/inbox"), alias="MEDIA_GATEWAY_INBOX_DIR"
    )
    outbox_dir: Path = Field(
        default=Path("~/media/outbox"), alias="MEDIA_GATEWAY_OUTBOX_DIR"
    )
    max_upload_mb: int = Field(default=200, alias="MEDIA_GATEWAY_MAX_UPLOAD_MB")
    allowed_extensions: list[str] = Field(
        default_factory=lambda: list(ALLOWED_CONTENT_TYPES),
        alias="MEDIA_GATEWAY_ALLOWED_EXTENSIONS",
    )

    comfy_url: str = Field(
        default="http://127.0.0.1:8188", alias="MEDIA_GATEWAY_COMFY_URL"
    )
    comfy_input_dir: Path = Field(
        default=Path("~/ComfyUI/input"), alias="MEDIA_GATEWAY_COMFY_INPUT_DIR"
    )
    comfy_output_dir: Path = Field(
        default=Path("~/ComfyUI/output"), alias="MEDIA_GATEWAY_COMFY_OUTPUT_DIR"
    )
    workflows_dir: Path = Field(
        default_factory=_default_workflows_dir,
        alias="MEDIA_GATEWAY_WORKFLOWS_DIR",
    )
    litellm_url: str = Field(
        default="http://127.0.0.1:8083/v1", alias="MEDIA_GATEWAY_LITELLM_URL"
    )
    litellm_key: str = Field(default="", alias="MEDIA_GATEWAY_LITELLM_KEY")
    qwen_model: str = Field(default="qwen-vl", alias="MEDIA_GATEWAY_QWEN_MODEL")
    qwen_max_tokens: int = Field(
        default=512, alias="MEDIA_GATEWAY_QWEN_MAX_TOKENS"
    )

    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", alias="LANGFUSE_HOST"
    )

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def _split_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "inbox_dir",
        "outbox_dir",
        "comfy_input_dir",
        "comfy_output_dir",
        "workflows_dir",
        mode="after",
    )
    @classmethod
    def _expand_path(cls, value: Path) -> Path:
        return _expanded(value)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def auth_enabled(self) -> bool:
        return bool(self.token)
