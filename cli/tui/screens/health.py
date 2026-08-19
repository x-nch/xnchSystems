"""System health dashboard screen."""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Header, Button
from textual import work

logger = logging.getLogger(__name__)


class HealthScreen(Screen):
    """System health dashboard with auto-refresh."""

    DEFAULT_CSS = """
    HealthScreen {
        layout: vertical;
        height: 1fr;
        padding: 1;
    }
    #health-content {
        height: 1fr;
        overflow-y: auto;
    }
    #health-controls {
        height: 3;
        dock: bottom;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading health data...", id="health-content")
        yield Button("Refresh", id="btn-refresh", variant="primary")

    async def on_mount(self) -> None:
        await self._refresh_health()
        self.set_interval(self.app.config.health_poll_interval_s, self._refresh_health)

    async def _refresh_health(self) -> None:
        try:
            xnch_health = await self.app.client.health()
            nexi_health = await self.app.client.nexi_health()
            state = await self.app.client.system_state()

            xnch_status = xnch_health.get("status", "unknown")
            xnch_version = xnch_health.get("version", "?")
            redis = xnch_health.get("redis", "unknown")
            nexi_status = nexi_health.get("status", "unknown")
            state_ver = state.get("system_state_version", "?")
            policy_ver = state.get("policy_version", "?")

            content = f"""System Health

xnch:    {"●" if xnch_status == "ok" else "○"} {xnch_status}    v{xnch_version}
nexi:    {"●" if nexi_status == "ok" else "○"} {nexi_status}    v0.1.0
redis:   {"●" if redis == "ok" else "○"} {redis}

state:   {state_ver}
policy:  {policy_ver}"""

            self.query_one("#health-content", Static).update(content)

            self.app.state.health_status = {
                "xnch": xnch_health,
                "nexi": nexi_health,
            }
            self.app.state.connected = xnch_status == "ok"
        except Exception as exc:
            logger.error("Health check failed: %s", exc)
            self.query_one("#health-content", Static).update(f"Health check failed: {exc}")

    async def on_button_pressed(self, event) -> None:
        if event.button.id == "btn-refresh":
            await self._refresh_health()
