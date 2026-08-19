"""Streaming markdown renderer widget for chat messages."""

from __future__ import annotations

from rich.markdown import Markdown as RichMarkdown
from textual.widget import Widget
from textual.widgets import RichLog


class StreamingMarkdown(Widget):
    """A widget that renders markdown incrementally as tokens arrive."""

    DEFAULT_CSS = """
    StreamingMarkdown {
        height: auto;
        max-height: 1fr;
        overflow-y: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._full_text: str = ""
        self._log: RichLog | None = None

    def compose(self):
        self._log = RichLog(markup=True, wrap=True, highlight=True)
        yield self._log

    def append_token(self, token: str) -> None:
        """Append a streaming token and re-render."""
        self._full_text += token
        self._rendermarkdown()

    def set_text(self, text: str) -> None:
        """Replace the full content and re-render."""
        self._full_text = text
        self._rendermarkdown()

    def clear(self) -> None:
        """Clear all content."""
        self._full_text = ""
        if self._log:
            self._log.clear()

    def _rendermarkdown(self) -> None:
        if self._log and self._full_text:
            self._log.clear()
            self._log.write(RichMarkdown(self._full_text))
