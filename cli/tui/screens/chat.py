"""Streaming chat screen — primary interaction with Nexi."""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static, TextArea, Header

from ..widgets.markdown import StreamingMarkdown

logger = logging.getLogger(__name__)


def parse_slash_command(text: str) -> dict[str, str] | None:
    """Parse a /command from chat input. Returns None if not a command."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split(maxsplit=1)
    command = parts[0][1:]  # remove leading /
    args = parts[1] if len(parts) > 1 else ""
    return {"command": command, "args": args}


class ChatScreen(Screen):
    """Streaming chat screen with Nexi."""

    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
        height: 1fr;
    }
    #chat-messages {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    #chat-input-area {
        height: 5;
        min-height: 3;
        dock: bottom;
        padding: 0 1;
    }
    #chat-input {
        height: 1fr;
    }
    .msg-user {
        text-style: bold;
        color: $accent;
    }
    .msg-nexi {
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("", id="chat-messages"),
            id="chat-messages",
        )
        yield Vertical(
            TextArea(id="chat-input", placeholder="Type a message... (Ctrl+Enter to send)"),
            id="chat-input-area",
        )

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#chat-input", TextArea).focus()

    async def on_text_area_submitted(self, event: TextArea.Submitted) -> None:
        """Handle message submission."""
        text = event.text_area.text.strip()
        if not text:
            return

        event.text_area.text = ""

        # Check for slash commands
        cmd = parse_slash_command(text)
        if cmd:
            await self._handle_command(cmd)
            return

        # Add user message to display
        self._append_message("you", text)

        # Stream response from Nexi
        self._append_message("nexi", "")
        await self._stream_response(text)

    async def _stream_response(self, message: str) -> None:
        """Stream a chat response from Nexi."""
        app = self.app
        client = app.client
        state = app.state

        messages_container = self.query_one("#chat-messages")
        nexi_static = messages_container.query_all("Static")[-1]

        full_text = ""

        def on_token(token: str) -> None:
            nonlocal full_text
            full_text += token
            nexi_static.update(f"nexi> {full_text}")

        try:
            result = await client.chat_stream(
                message,
                session_id=state.current_session_id,
                on_token=on_token,
            )
            state.increment_message_count()
        except Exception as exc:
            logger.error("Chat stream failed: %s", exc)
            nexi_static.update(f"nexi> [error] {exc}")

    async def _handle_command(self, cmd: dict[str, str]) -> None:
        """Handle slash commands."""
        command = cmd["command"]
        args = cmd["args"]

        if command == "quit":
            self.app.exit()
        elif command == "session":
            if args == "new":
                self.app.action_new_session()
            elif args == "list":
                self.app.push_screen("sessions")
        elif command == "recall":
            self.app.push_screen("memory")
        elif command == "health":
            self.app.push_screen("health")
        elif command == "tools":
            self.app.push_screen("tools")
        elif command == "voice":
            self._append_message("system", "Voice mode not yet implemented")
        elif command == "json":
            self._append_message("system", "JSON mode toggled")
        else:
            self._append_message("system", f"Unknown command: /{command}")

    def _append_message(self, role: str, content: str) -> None:
        """Append a message to the chat display."""
        messages = self.query_one("#chat-messages")
        if role == "nexi":
            messages.append(Static(f"nexi> {content}", classes="msg-nexi"))
        elif role == "you":
            messages.append(Static(f"you> {content}", classes="msg-user"))
        else:
            messages.append(Static(f"[{role}] {content}"))
