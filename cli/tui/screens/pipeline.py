"""Decision pipeline view screen — inspect session/init results."""

from __future__ import annotations

import json
import logging
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Header, TextArea, Button
from textual.containers import Vertical

logger = logging.getLogger(__name__)


class PipelineScreen(Screen):
    """Decision pipeline inspection screen."""

    DEFAULT_CSS = """
    PipelineScreen {
        layout: vertical;
        height: 1fr;
        padding: 1;
    }
    #pipeline-input {
        height: 5;
        dock: top;
        padding: 0 1;
    }
    #pipeline-result {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            TextArea(placeholder="Enter test input for session/init...", id="pipeline-input"),
            Button("Run Pipeline", id="btn-run", variant="primary"),
            id="pipeline-controls",
        )
        yield Static("Enter input and click Run to inspect the decision pipeline", id="pipeline-result")

    async def on_button_pressed(self, event) -> None:
        if event.button.id == "btn-run":
            input_text = self.query_one("#pipeline-input", TextArea).text.strip()
            if not input_text:
                return

            try:
                result = await self.app.client.chat(input_text, session_id=self.app.state.current_session_id)
                formatted = json.dumps(result, indent=2)
                self.query_one("#pipeline-result", Static).update(formatted[:3000])
            except Exception as exc:
                logger.error("Pipeline test failed: %s", exc)
                self.query_one("#pipeline-result", Static).update(f"Error: {exc}")
