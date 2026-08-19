"""Navigation sidebar widget."""

from __future__ import annotations

from textual.widget import Widget
from textual.widgets import Static, Button
from textual.containers import Vertical


class Sidebar(Widget):
    """Left sidebar with navigation buttons."""

    DEFAULT_CSS = """
    Sidebar {
        width: 24;
        height: 1fr;
        background: $surface;
    }
    Sidebar .nav-title {
        height: 1;
        text-style: bold;
        color: $primary;
        padding: 0 1;
    }
    Sidebar Button {
        width: 100%;
        height: 3;
        margin: 0;
        background: transparent;
        text-align: left;
        padding-left: 1;
    }
    Sidebar Button:hover {
        background: $primary 10%;
    }
    Sidebar Button.-active {
        background: $primary 20%;
        text-style: bold;
    }
    """

    def compose(self):
        yield Static(" xnch tui", classes="nav-title")
        yield Button("Chat", id="nav-chat", classes="nav-button")
        yield Button("Memory", id="nav-memory", classes="nav-button")
        yield Button("Sessions", id="nav-sessions", classes="nav-button")
        yield Button("Tools", id="nav-tools", classes="nav-button")
        yield Button("Health", id="nav-health", classes="nav-button")
        yield Button("Pipeline", id="nav-pipeline", classes="nav-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button presses to screen switching."""
        screen_map = {
            "nav-chat": "chat",
            "nav-memory": "memory",
            "nav-sessions": "sessions",
            "nav-tools": "tools",
            "nav-health": "health",
            "nav-pipeline": "pipeline",
        }
        screen_name = screen_map.get(event.button.id)
        if screen_name:
            self.app.push_screen(screen_name)
