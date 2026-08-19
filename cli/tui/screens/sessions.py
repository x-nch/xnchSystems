"""Session management screen — view, create, switch sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Header, DataTable, Button
from textual.containers import Horizontal

_STATE_PATH = Path("~/.xnch/cli_state.json").expanduser()


class SessionsScreen(Screen):
    """Session management screen."""

    DEFAULT_CSS = """
    SessionsScreen {
        layout: vertical;
        height: 1fr;
    }
    #session-list {
        height: 1fr;
        padding: 1;
    }
    #session-actions {
        height: 3;
        dock: bottom;
        padding: 0 1;
    }
    #session-actions Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="session-list")
        yield Horizontal(
            Button("New Session", id="btn-new", variant="primary"),
            Button("Clear Session", id="btn-clear", variant="warning"),
            id="session-actions",
        )

    def on_mount(self) -> None:
        table = self.query_one("#session-list", DataTable)
        table.add_columns("Active", "Session ID")
        self._load_sessions()

    def _load_sessions(self) -> None:
        table = self.query_one("#session-list", DataTable)
        table.clear()
        try:
            if _STATE_PATH.exists():
                data = json.loads(_STATE_PATH.read_text())
                current = data.get("session_id", "")
                table.add_row("●" if current else "", current)
        except (json.JSONDecodeError, OSError):
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-new":
            session_id = await self.app.client.new_session()
            self.app.state.current_session_id = session_id
            self.app.state.reset_message_count()
            self._load_sessions()
            self.app.push_screen("chat")
        elif event.button.id == "btn-clear":
            session_id = await self.app.client.clear_session()
            self.app.state.current_session_id = session_id
            self.app.state.reset_message_count()
            self._load_sessions()
