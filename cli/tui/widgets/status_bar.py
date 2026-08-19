"""Bottom status bar widget."""

from __future__ import annotations

from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """Bottom status bar showing health, session, and message count."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """

    def compose(self):
        yield Static(self._build_text(), id="status-text")

    def _build_text(self) -> str:
        state = self.app.state
        xnch_dot = "●" if state.connected else "○"
        nexi_health = state.health_status.get("nexi", {})
        nexi_dot = "●" if nexi_health.get("status") == "ok" else "○"
        redis = state.health_status.get("redis", "unknown")
        redis_dot = "●" if redis == "ok" else "○"
        session = state.current_session_id or "new"
        msgs = state.message_count
        model = state.model_name or "—"
        return (
            f" xnch:{xnch_dot} nexi:{nexi_dot} redis:{redis_dot}"
            f" | session: {session} | msgs: {msgs} | model: {model}"
            f" | Ctrl+Q:quit"
        )

    def refresh_status(self) -> None:
        """Re-render the status text."""
        text = self.query_one("#status-text", Static)
        text.update(self._build_text())
