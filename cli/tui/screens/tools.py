"""MCP tools browser screen — list, filter, invoke tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Header, DataTable, TextArea, Button, Label
from textual.containers import Vertical, Horizontal

from ..widgets.search_input import SearchInput

logger = logging.getLogger(__name__)


class ToolsScreen(Screen):
    """MCP tools browser screen."""

    DEFAULT_CSS = """
    ToolsScreen {
        layout: vertical;
        height: 1fr;
    }
    #tools-search {
        height: 3;
        dock: top;
        padding: 0 1;
    }
    #tools-list {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    #tools-invoke {
        height: auto;
        max-height: 40%;
        padding: 1;
        border-top: solid $primary;
    }
    #tools-result {
        height: auto;
        max-height: 30%;
        padding: 1;
        border-top: solid $accent;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tools: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield SearchInput(placeholder="Filter tools...", id="tools-search")
        yield DataTable(id="tools-list")
        yield Vertical(
            Label("Invoke:"),
            TextArea(id="invoke-name", placeholder="tool name"),
            TextArea(id="invoke-args", placeholder='{"key": "value"}'),
            Button("Invoke", id="btn-invoke", variant="primary"),
            id="tools-invoke",
        )
        yield Static("Results appear here", id="tools-result")

    async def on_mount(self) -> None:
        table = self.query_one("#tools-list", DataTable)
        table.add_columns("Name", "Tier", "Source")
        try:
            data = await self.app.client.mcp_tools(actor_role=self.app.config.mcp_actor_role)
            self._tools = data.get("tools", [])
            self._display_tools(self._tools)
        except Exception as exc:
            logger.error("Failed to load MCP tools: %s", exc)

    def _display_tools(self, tools: list[dict[str, Any]]) -> None:
        table = self.query_one("#tools-list", DataTable)
        table.clear()
        for tool in tools:
            name = tool.get("name", "")
            tier = tool.get("tier", "")
            source = "native" if not name.startswith("crg_") else "bridged"
            table.add_row(name, str(tier), source)

    async def on_input_submitted(self, event) -> None:
        """Filter tools by search input."""
        query = event.value.strip().lower()
        if not query:
            self._display_tools(self._tools)
            return
        filtered = [t for t in self._tools if query in t.get("name", "").lower()]
        self._display_tools(filtered)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-invoke":
            name = self.query_one("#invoke-name", TextArea).text.strip()
            args_text = self.query_one("#invoke-args", TextArea).text.strip()
            if not name:
                return
            try:
                args = json.loads(args_text) if args_text else {}
            except json.JSONDecodeError:
                self.query_one("#tools-result", Static).update("Invalid JSON in arguments")
                return

            try:
                result = await self.app.client.mcp_call(name, args, actor_role=self.app.config.mcp_actor_role)
                self.query_one("#tools-result", Static).update(json.dumps(result, indent=2)[:2000])
            except Exception as exc:
                self.query_one("#tools-result", Static).update(f"Error: {exc}")
