"""Reactive state model for the TUI dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TuiState:
    """Centralized reactive state for TUI screens.

    Textual screens bind to these properties and re-render on change.
    Uses plain dataclass — Textual's reactive descriptors are applied
    at the App level where screens are composed.
    """

    current_session_id: str = ""
    health_status: dict = field(default_factory=dict)
    connected: bool = False
    message_count: int = 0
    model_name: str = ""
    current_screen: str = "chat"
    mcp_tools: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    detail_visible: bool = False

    def increment_message_count(self) -> None:
        self.message_count += 1

    def reset_message_count(self) -> None:
        self.message_count = 0
