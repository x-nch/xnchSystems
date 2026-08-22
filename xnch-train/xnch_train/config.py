"""xnch-train settings — XTRAIN_ env prefix, Node-A filesystem dataset home."""
from pathlib import Path
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class _IgnoreNoneInitOverrides(PydanticBaseSettingsSource):
    """Init source that treats explicit ``None`` kwargs as "no override"."""

    def __init__(self, inner: PydanticBaseSettingsSource) -> None:
        super().__init__(inner.settings_cls, inner._init_state)
        self._inner = inner

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._inner.get_field_value(field, field_name)

    def __call__(self) -> dict[str, Any]:
        return {key: value for key, value in self._inner().items() if value is not None}


class XtrainSettings(BaseSettings):
    """Configuration for the xnch-train worker (Phase 0 surfaces only)."""

    model_config = SettingsConfigDict(env_prefix="XTRAIN_", env_file=".env", extra="ignore")

    dataset_dir: Path = Path("./datasets")
    postgres_url: str = "postgresql://localhost:5432/xnch"
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    pseudonymize_secret: str = ""
    gate_epsilon: float = 0.02
    serving_regression_bound_pct: float = 10.0
    extract_page_size: int = 100

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Drop explicit None init overrides so env/dotenv/defaults still apply."""
        return (
            _IgnoreNoneInitOverrides(init_settings),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    def pseudonymize_key(self) -> bytes:
        """Deterministic HMAC key for entity pseudonymization."""
        return self.pseudonymize_secret.encode("utf-8")
