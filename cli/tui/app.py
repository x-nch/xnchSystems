"""Main TUI application — layout, screen routing, lifecycle."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from .client import AsyncXnchClient
from .config import TuiConfig
from .state import TuiState
from .screens import (
    ChatScreen, MemoryScreen, SessionsScreen,
    ToolsScreen, HealthScreen, PipelineScreen,
)
from .widgets.sidebar import Sidebar
from .widgets.status_bar import StatusBar

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class XnchTuiApp(App):
    """Textual TUI for interacting with xnch/nexi."""

    TITLE = "xnch tui"
    SUB_TITLE = "control plane dashboard"

    CSS = """
    Screen {
        layout: horizontal;
        height: 1fr;
    }
    #sidebar {
        width: 24;
        min-width: 4;
        max-width: 40;
        background: $surface;
        border-right: solid $primary;
    }
    #main-content {
        width: 1fr;
        height: 1fr;
    }
    #detail-panel {
        width: 40;
        min-width: 0;
        max-width: 60;
        background: $surface-darken-1;
        border-left: solid $primary;
        display: none;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        background: $primary;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+n", "new_session", "New Session"),
        Binding("ctrl+r", "focus_recall", "Recall"),
        Binding("ctrl+m", "switch_screen('memory')", "Memory"),
        Binding("ctrl+h", "switch_screen('health')", "Health"),
        Binding("ctrl+t", "switch_screen('tools')", "Tools"),
        Binding("tab", "toggle_detail", "Toggle Detail"),
    ]

    SCREENS = {
        "chat": ChatScreen,
        "memory": MemoryScreen,
        "sessions": SessionsScreen,
        "tools": ToolsScreen,
        "health": HealthScreen,
        "pipeline": PipelineScreen,
    }

    def __init__(self, config: TuiConfig | None = None) -> None:
        super().__init__()
        self.config = config or TuiConfig()
        self.state = TuiState()
        self.client = AsyncXnchClient()

    async def on_mount(self) -> None:
        """Initialize state from API on startup."""
        try:
            health = await self.client.health()
            self.state.health_status = health
            self.state.connected = health.get("status") == "ok"
            self.state.current_session_id = self.client.current_session_id()
        except Exception as exc:
            logger.warning("Failed to fetch initial health: %s", exc)
            self.state.connected = False

        self.push_screen("chat")

    def compose(self) -> ComposeResult:
        yield Sidebar(id="sidebar")
        yield Static("Loading...", id="main-content")
        yield Static("", id="detail-panel")
        yield StatusBar(id="status-bar")

    def action_new_session(self) -> None:
        """Create a new session."""
        self.run_worker(self._create_session())

    async def _create_session(self) -> None:
        session_id = await self.client.new_session()
        self.state.current_session_id = session_id
        self.state.reset_message_count()
        self.push_screen("chat")

    def action_toggle_detail(self) -> None:
        """Toggle the detail panel visibility."""
        panel = self.query_one("#detail-panel")
        self.state.detail_visible = not self.state.detail_visible
        panel.display = self.state.detail_visible

    def action_focus_recall(self) -> None:
        """Switch to memory screen with focus on search."""
        self.push_screen("memory")
