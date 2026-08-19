"""TUI-specific configuration: keybindings, poll intervals, defaults."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiConfig:
    health_poll_interval_s: float = 30.0
    max_chat_history: int = 200
    sidebar_width: int = 24
    detail_panel_width: int = 40
    default_top_k: int = 5
    mcp_actor_role: str = "nexi"

    key_quit: str = "ctrl+q"
    key_new_session: str = "ctrl+n"
    key_recall: str = "ctrl+r"
    key_memory: str = "ctrl+m"
    key_health: str = "ctrl+h"
    key_tools: str = "ctrl+t"
    key_voice: str = "ctrl+v"
    key_toggle_detail: str = "tab"
    key_close_detail: str = "escape"
