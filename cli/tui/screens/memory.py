"""Memory recall screen — semantic search over episodic memory."""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Static, Header, DataTable

from ..widgets.search_input import SearchInput

logger = logging.getLogger(__name__)


class MemoryScreen(Screen):
    """Memory recall screen with search and results."""

    DEFAULT_CSS = """
    MemoryScreen {
        layout: vertical;
        height: 1fr;
    }
    #memory-search {
        height: 3;
        dock: top;
        padding: 0 1;
    }
    #memory-results {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    #memory-detail {
        height: auto;
        max-height: 1fr;
        padding: 1;
        border-top: solid $primary;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield SearchInput(placeholder="Search memory... (paste or type query)", id="memory-search")
        yield DataTable(id="memory-results")
        yield Static("Select a result to view details", id="memory-detail")

    def on_mount(self) -> None:
        table = self.query_one("#memory-results", DataTable)
        table.add_columns("Sim", "Type", "Content")
        self.query_one("#memory-search", SearchInput).focus()

    async def on_input_submitted(self, event) -> None:
        """Handle search submission."""
        query = event.value.strip()
        if not query:
            return

        client = self.app.client
        try:
            results = await client.memory_recall(query, top_k=self.app.config.default_top_k)
            self._display_results(results)
        except Exception as exc:
            logger.error("Memory recall failed: %s", exc)
            self.query_one("#memory-detail", Static).update(f"Error: {exc}")

    def _display_results(self, results: list[dict[str, Any]]) -> None:
        """Populate the results table."""
        table = self.query_one("#memory-results", DataTable)
        table.clear()
        for item in results:
            sim = f"{item.get('similarity', 0.0):.3f}"
            type_ = item.get("type", "unknown")
            content = (item.get("content", "")[:100] + "...") if len(item.get("content", "")) > 100 else item.get("content", "")
            table.add_row(sim, type_, content)

    def on_data_table_row_selected(self, event) -> None:
        """Show detail for selected result."""
        # The full content is available in the row data
        # For now, show a placeholder — full implementation would
        # store the full result objects and display them here
        self.query_one("#memory-detail", Static).update(
            f"Row {event.row_index} selected — detail view coming soon"
        )
