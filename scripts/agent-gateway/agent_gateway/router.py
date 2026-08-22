"""Route OpenAI model names to agent backends."""

from __future__ import annotations

from dataclasses import dataclass

from .adapters import ClaudeCodeAdapter, CursorAgentAdapter, OpenCodeAdapter
from .adapters.base import AgentAdapter
from .config import settings

BACKENDS: dict[str, AgentAdapter] = {
    "claude-code": ClaudeCodeAdapter(),
    "opencode": OpenCodeAdapter(),
    "cursor-agent": CursorAgentAdapter(),
}

MODEL_CATALOG: list[tuple[str, str, str]] = [
    ("claude-code/sonnet", "claude-code", "anthropic"),
    ("claude-code/opus", "claude-code", "anthropic"),
    ("claude-code/haiku", "claude-code", "anthropic"),
    ("opencode/build", "opencode", "opencode"),
    ("opencode/plan", "opencode", "opencode"),
    ("cursor-agent/composer-2.5", "cursor-agent", "cursor"),
    ("cursor-agent/cursor-grok-4.5-medium", "cursor-agent", "cursor"),
]


@dataclass
class RoutedModel:
    backend: str
    model: str | None
    model_id: str


def route_model(model: str) -> RoutedModel:
    """Parse `backend/model` or fall back to default backend."""
    normalized = model.strip()
    if "/" in normalized:
        backend, submodel = normalized.split("/", 1)
        backend = backend.lower()
        if backend in BACKENDS:
            return RoutedModel(backend=backend, model=submodel or None, model_id=normalized)

    lowered = normalized.lower()
    if lowered in BACKENDS:
        return RoutedModel(backend=lowered, model=None, model_id=lowered)

    default = settings.default_backend
    if default not in BACKENDS:
        raise ValueError(f"Unknown default backend: {default}")

    return RoutedModel(backend=default, model=normalized or None, model_id=f"{default}/{normalized}")


def get_adapter(backend: str) -> AgentAdapter:
    adapter = BACKENDS.get(backend)
    if adapter is None:
        known = ", ".join(sorted(BACKENDS))
        raise ValueError(f"Unknown backend '{backend}'. Expected one of: {known}")
    return adapter
