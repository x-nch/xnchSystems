# TUI Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Textual-based TUI dashboard for interacting with the xnch control plane and nexi decision engine, with streaming chat, memory recall, session management, MCP tools, health monitoring, and voice I/O.

**Architecture:** Extend the existing `cli/` package with a `cli/tui/` sub-package. Reuse `XnchCliClient` via an async adapter. Textual provides the layout engine, widgets, and screen management. Each feature is a separate `Screen` subclass. SSE streaming uses `httpx.AsyncClient.stream()` in Textual workers.

**Tech Stack:** Python 3.13+, Textual (>=0.40), Rich (>=13.0), httpx, pytest

**Spec:** `docs/superpowers/specs/2026-08-19-tui-dashboard-design.md`

## Global Constraints

- Python 3.13+ (`requires-python = ">=3.13"`)
- `textual>=0.40` — new dependency, add to `pyproject.toml`
- `rich>=13.0` — already available via textual dependency
- Reuse existing `cli/client.py` (XnchCliClient) and `cli/config.py` (CliConfig) — do not duplicate
- No absolute imports from sibling packages (follow `AGENTS.md` conventions)
- Use `logging.getLogger(__name__)` for loggers
- Pydantic models for request/response types where applicable
- pytest with `asyncio_mode = "auto"` (from `pyproject.toml`)

## File Structure

```
cli/tui/
  __init__.py              # Package marker, version
  app.py                   # Main Textual App class
  state.py                 # Reactive state model
  client.py                # Async adapter wrapping XnchCliClient
  config.py                # TUI-specific config (keybindings, intervals)
  screens/
    __init__.py            # Screen registry
    chat.py                # Streaming chat screen
    memory.py              # Memory recall screen
    sessions.py            # Session management screen
    tools.py               # MCP tools browser screen
    health.py              # System health dashboard screen
    pipeline.py            # Decision pipeline view screen
  widgets/
    __init__.py
    markdown.py            # Streaming markdown renderer
    status_bar.py          # Bottom status bar
    sidebar.py             # Navigation sidebar
    search_input.py        # Search input with paste
cli/__main__.py            # Add 'tui' subcommand entry
cli/main.py                # Register tui subcommand
tests/test_tui_client.py   # Client adapter tests
tests/test_tui_state.py    # State model tests
tests/test_tui_app.py      # App composition tests
tests/test_tui_widgets.py  # Widget unit tests
tests/test_tui_screens.py  # Screen tests
```

---

### Task 1: Add Textual dependency + package scaffold

**Files:**
- Modify: `pyproject.toml`
- Create: `cli/tui/__init__.py`

**Interfaces:**
- Consumes: existing `pyproject.toml` dependencies
- Produces: `textual>=0.40` available, `cli/tui/` package exists

- [ ] **Step 1: Add textual to pyproject.toml dependencies**

```toml
# In pyproject.toml, add to dependencies list:
    "textual>=0.40",
```

- [ ] **Step 2: Create cli/tui/__init__.py**

```python
"""xnch TUI — Textual-based terminal dashboard for xnch/nexi."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Verify textual installs**

Run: `pip install -e ".[dev]"` (or `uv sync`)
Expected: textual installs without conflicts

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml cli/tui/__init__.py
git commit -m "feat(tui): add textual dependency and package scaffold"
```

---

### Task 2: Async client adapter

**Files:**
- Create: `cli/tui/client.py`
- Create: `tests/test_tui_client.py`

**Interfaces:**
- Consumes: `cli/client.py::XnchCliClient`, `cli/config.py::CliConfig`
- Produces: `AsyncXnchClient` class with async methods matching all API endpoints

- [ ] **Step 1: Write failing test for AsyncXnchClient.health**

```python
# tests/test_tui_client.py
"""Tests for the async TUI client adapter."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cli.tui.client import AsyncXnchClient


@pytest.fixture
def mock_sync_client():
    """Mock XnchCliClient for testing."""
    client = MagicMock()
    client.health.return_value = {"status": "ok", "version": "0.1.0"}
    client.nexi_health.return_value = {"status": "ok"}
    client.system_state.return_value = {"system_state_version": "v1", "policy_version": "v2"}
    client.chat.return_value = {"response": "hello", "model_used": "gpt-4o", "session_id": "test-123"}
    client.memory_recall.return_value = [{"id": "ep1", "content": "test episode", "similarity": 0.9}]
    client.memory_surface.return_value = []
    client.mcp_tools.return_value = {"tools": [{"name": "test_tool"}], "actor": "nexi"}
    client.mcp_servers.return_value = {"enabled": True, "servers": []}
    client.mcp_call.return_value = {"result": "ok"}
    return client


@pytest.fixture
def async_client(mock_sync_client):
    """Create AsyncXnchClient with mocked sync client."""
    client = AsyncXnchClient.__new__(AsyncXnchClient)
    client._sync = mock_sync_client
    return client


async def test_health(async_client):
    result = await async_client.health()
    assert result["status"] == "ok"


async def test_nexi_health(async_client):
    result = await async_client.nexi_health()
    assert result["status"] == "ok"


async def test_system_state(async_client):
    result = await async_client.system_state()
    assert "system_state_version" in result


async def test_chat(async_client):
    result = await async_client.chat("hello", session_id="test-123")
    assert result["response"] == "hello"


async def test_memory_recall(async_client):
    results = await async_client.memory_recall("test query")
    assert len(results) == 1
    assert results[0]["id"] == "ep1"


async def test_mcp_tools(async_client):
    data = await async_client.mcp_tools()
    assert len(data["tools"]) == 1


async def test_mcp_call(async_client):
    result = await async_client.mcp_call("test_tool", {"arg": "val"})
    assert result["result"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_client.py -v`
Expected: FAIL with ImportError (module not found)

- [ ] **Step 3: Implement AsyncXnchClient**

```python
# cli/tui/client.py
"""Async adapter wrapping the synchronous XnchCliClient for Textual workers."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import httpx

from cli.client import XnchCliClient
from cli.config import CliConfig


class AsyncXnchClient:
    """Async wrapper over XnchCliClient for Textual workers.

    Uses asyncio.to_thread for synchronous httpx calls,
    and httpx.AsyncClient for SSE streaming.
    """

    def __init__(self, config: CliConfig | None = None) -> None:
        self.config = config or CliConfig.from_env()
        self._sync = XnnchCliClient(self.config)
        self._stream_client = httpx.AsyncClient(
            base_url=self.config.nexi_url, timeout=120.0
        )

    async def close(self) -> None:
        self._sync.close()
        await self._stream_client.aclose()

    # ── Health ──────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.health)

    async def nexi_health(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.nexi_health)

    async def system_state(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.system_state)

    # ── Chat ────────────────────────────────────────────────────────

    async def chat(
        self, message: str, *, session_id: str | None = None, actor_role: str | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.chat, message, session_id=session_id, actor_role=actor_role)

    async def chat_stream(
        self,
        message: str,
        *,
        session_id: str | None = None,
        actor_role: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """Stream chat via SSE, calling on_token for each content delta."""
        sid = session_id or self._sync._load_session_id()
        full_text = ""

        async with self._stream_client.stream(
            "POST",
            "/nexi/chat/stream",
            json={
                "session_id": sid,
                "message": message,
                "actor_role": actor_role or self.config.actor,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ")
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "error" in chunk:
                    raise RuntimeError(chunk["error"])
                delta = chunk.get("content", "")
                if delta:
                    full_text += delta
                    if on_token:
                        on_token(delta)

        self._sync._save_session_id(sid)
        return full_text

    # ── Memory ──────────────────────────────────────────────────────

    async def memory_recall(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sync.memory_recall, query, top_k=top_k)

    async def memory_surface(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sync.memory_surface)

    # ── Session ─────────────────────────────────────────────────────

    async def new_session(self) -> str:
        return await asyncio.to_thread(self._sync.new_session)

    async def clear_session(self) -> str:
        return await asyncio.to_thread(self._sync.clear_session)

    def current_session_id(self) -> str:
        return self._sync._load_session_id()

    # ── MCP ─────────────────────────────────────────────────────────

    async def mcp_tools(self, *, actor_role: str | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.mcp_tools, actor_role=actor_role)

    async def mcp_servers(self, *, actor_role: str | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.mcp_servers, actor_role=actor_role)

    async def mcp_call(
        self, name: str, arguments: dict[str, Any] | None = None, *, actor_role: str | None = None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.mcp_call, name, arguments, actor_role=actor_role)

    # ── Token ───────────────────────────────────────────────────────

    async def mint_token(self, *, actor: str | None = None, ttl_s: int = 3600) -> str:
        return await asyncio.to_thread(self._sync.mint_token, actor=actor, ttl_s=ttl_s)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tui_client.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cli/tui/client.py tests/test_tui_client.py
git commit -m "feat(tui): add async client adapter wrapping XnchCliClient"
```

---

### Task 3: Reactive state model

**Files:**
- Create: `cli/tui/state.py`
- Create: `tests/test_tui_state.py`

**Interfaces:**
- Consumes: nothing (standalone)
- Produces: `TuiState` class with reactive properties

- [ ] **Step 1: Write failing test for TuiState**

```python
# tests/test_tui_state.py
"""Tests for the TUI reactive state model."""

from __future__ import annotations

from cli.tui.state import TuiState


def test_initial_state():
    state = TuiState()
    assert state.current_session_id == ""
    assert state.health_status == {}
    assert state.connected is False
    assert state.message_count == 0
    assert state.model_name == ""
    assert state.current_screen == "chat"


def test_session_update():
    state = TuiState()
    state.current_session_id = "cli-abc123"
    assert state.current_session_id == "cli-abc123"


def test_health_update():
    state = TuiState()
    state.health_status = {"xnch": "ok", "nexi": "ok"}
    assert state.health_status["xnch"] == "ok"


def test_increment_message_count():
    state = TuiState()
    state.increment_message_count()
    assert state.message_count == 1
    state.increment_message_count()
    assert state.message_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_state.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement TuiState**

```python
# cli/tui/state.py
"""Reactive state model for the TUI dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TuiState:
    """Centralized reactive state for TUI screens.

    Textual screens bind to these properties and re-render on change.
    Uses plain dataclass — Textual's reactive descriptors are applied
    at the App level where screens are composed.
    """

    current_session_id: str = ""
    health_status: dict = field(default_factory=dict)
    connected: bool = False
    message_count: int = 0
    model_name: str = ""
    current_screen: str = "chat"
    mcp_tools: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    detail_visible: bool = False

    def increment_message_count(self) -> None:
        self.message_count += 1

    def reset_message_count(self) -> None:
        self.message_count = 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tui_state.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cli/tui/state.py tests/test_tui_state.py
git commit -m "feat(tui): add reactive state model"
```

---

### Task 4: TUI config (keybindings, intervals)

**Files:**
- Create: `cli/tui/config.py`

**Interfaces:**
- Consumes: nothing (standalone)
- Produces: `TuiConfig` dataclass with keybindings, poll intervals

- [ ] **Step 1: Implement TuiConfig**

```python
# cli/tui/config.py
"""TUI-specific configuration: keybindings, poll intervals, defaults."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TuiConfig:
    health_poll_interval_s: float = 30.0
    max_chat_history: int = 200
    sidebar_width: int = 24
    detail_panel_width: int = 40
    default_top_k: int = 5
    mcp_actor_role: str = "nexi"

    key_quit: str = "ctrl+q"
    key_new_session: str = "ctrl+n"
    key_recall: str = "ctrl+r"
    key_memory: str = "ctrl+m"
    key_health: str = "ctrl+h"
    key_tools: str = "ctrl+t"
    key_voice: str = "ctrl+v"
    key_toggle_detail: str = "tab"
    key_close_detail: str = "escape"
```

- [ ] **Step 2: Commit**

```bash
git add cli/tui/config.py
git commit -m "feat(tui): add TUI config with keybindings and intervals"
```

---

### Task 5: App shell with layout and screen routing

**Files:**
- Create: `cli/tui/app.py`
- Create: `cli/tui/screens/__init__.py`
- Create: `cli/tui/widgets/__init__.py`
- Create: `tests/test_tui_app.py`

**Interfaces:**
- Consumes: `AsyncXnchClient`, `TuiState`, `TuiConfig`
- Produces: `XnchTuiApp` class with layout, screen registry, compose method

- [ ] **Step 1: Write failing test for app composition**

```python
# tests/test_tui_app.py
"""Tests for TUI app composition."""

from __future__ import annotations

import pytest
from cli.tui.app import XnchTuiApp


async def test_app_creation():
    app = XnchTuiApp()
    assert app is not None


async def test_app_has_screens():
    app = XnchTuiApp()
    # App should define screen classes
    assert hasattr(app, "SCREENS") or hasattr(app, "compose")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_app.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create placeholder screen modules**

```python
# cli/tui/screens/__init__.py
"""TUI screen modules."""

from .chat import ChatScreen
from .memory import MemoryScreen
from .sessions import SessionsScreen
from .tools import ToolsScreen
from .health import HealthScreen
from .pipeline import PipelineScreen

__all__ = [
    "ChatScreen", "MemoryScreen", "SessionsScreen",
    "ToolsScreen", "HealthScreen", "PipelineScreen",
]
```

```python
# cli/tui/widgets/__init__.py
"""TUI widget modules."""
```

- [ ] **Step 4: Create placeholder screens (minimal stubs for app composition)**

Each screen file created as a minimal Textual Screen subclass. The full implementation comes in later tasks. For now, each screen just renders a title:

```python
# cli/tui/screens/chat.py — minimal stub
from textual.screen import Screen
from textual.widgets import Static

class ChatScreen(Screen):
    def compose(self):
        yield Static("Chat — Coming in Task 7")
```

```python
# cli/tui/screens/memory.py — minimal stub
from textual.screen import Screen
from textual.widgets import Static

class MemoryScreen(Screen):
    def compose(self):
        yield Static("Memory — Coming in Task 8")
```

```python
# cli/tui/screens/sessions.py — minimal stub
from textual.screen import Screen
from textual.widgets import Static

class SessionsScreen(Screen):
    def compose(self):
        yield Static("Sessions — Coming in Task 9")
```

```python
# cli/tui/screens/tools.py — minimal stub
from textual.screen import Screen
from textual.widgets import Static

class ToolsScreen(Screen):
    def compose(self):
        yield Static("Tools — Coming in Task 10")
```

```python
# cli/tui/screens/health.py — minimal stub
from textual.screen import Screen
from textual.widgets import Static

class HealthScreen(Screen):
    def compose(self):
        yield Static("Health — Coming in Task 11")
```

```python
# cli/tui/screens/pipeline.py — minimal stub
from textual.screen import Screen
from textual.widgets import Static

class PipelineScreen(Screen):
    def compose(self):
        yield Static("Pipeline — Coming in Task 12")
```

- [ ] **Step 5: Implement XnchTuiApp shell**

```python
# cli/tui/app.py
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
        background: $surface-dark;
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
```

- [ ] **Step 6: Implement Sidebar widget**

```python
# cli/tui/widgets/sidebar.py
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
        yield Button("💬 Chat", id="nav-chat", classes="nav-button")
        yield Button("🧠 Memory", id="nav-memory", classes="nav-button")
        yield Button("📋 Sessions", id="nav-sessions", classes="nav-button")
        yield Button("🔧 Tools", id="nav-tools", classes="nav-button")
        yield Button("💚 Health", id="nav-health", classes="nav-button")
        yield Button("⚙ Pipeline", id="nav-pipeline", classes="nav-button")

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
```

- [ ] **Step 7: Implement StatusBar widget**

```python
# cli/tui/widgets/status_bar.py
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_tui_app.py -v`
Expected: PASS

- [ ] **Step 9: Verify the app launches (manual)**

Run: `python -m cli.tui.app` (or add __main__.py)
Expected: TUI launches with sidebar and placeholder screens

- [ ] **Step 10: Commit**

```bash
git add cli/tui/app.py cli/tui/screens/ cli/tui/widgets/ tests/test_tui_app.py
git commit -m "feat(tui): add app shell with layout, sidebar, status bar, and screen routing"
```

---

### Task 6: Streaming markdown widget

**Files:**
- Create: `cli/tui/widgets/markdown.py`
- Create: `cli/tui/widgets/search_input.py`

**Interfaces:**
- Consumes: Rich's `Markdown` renderer
- Produces: `StreamingMarkdown` widget, `SearchInput` widget

- [ ] **Step 1: Implement StreamingMarkdown widget**

```python
# cli/tui/widgets/markdown.py
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
```

- [ ] **Step 2: Implement SearchInput widget**

```python
# cli/tui/widgets/search_input.py
"""Search input widget with paste support."""

from __future__ import annotations

from textual.widgets import Input


class SearchInput(Input):
    """Input widget that handles paste and multi-line input."""

    def __init__(self, placeholder: str = "Search...", **kwargs) -> None:
        super().__init__(placeholder=placeholder, **kwargs)
```

- [ ] **Step 3: Commit**

```bash
git add cli/tui/widgets/markdown.py cli/tui/widgets/search_input.py
git commit -m "feat(tui): add streaming markdown and search input widgets"
```

---

### Task 7: Chat screen (core feature)

**Files:**
- Create: `cli/tui/screens/chat.py` (replace stub)
- Create: `tests/test_tui_screens.py`

**Interfaces:**
- Consumes: `AsyncXnchClient`, `TuiState`, `StreamingMarkdown`
- Produces: Full chat screen with streaming, paste, slash commands

- [ ] **Step 1: Write test for chat message sending**

```python
# tests/test_tui_screens.py
"""Tests for TUI screens."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cli.tui.screens.chat import ChatScreen, parse_slash_command


def test_parse_slash_command_recall():
    cmd = parse_slash_command("/recall deployment yesterday")
    assert cmd is not None
    assert cmd["command"] == "recall"
    assert cmd["args"] == "deployment yesterday"


def test_parse_slash_command_session_new():
    cmd = parse_slash_command("/session new")
    assert cmd is not None
    assert cmd["command"] == "session"
    assert cmd["args"] == "new"


def test_parse_slash_command_quit():
    cmd = parse_slash_command("/quit")
    assert cmd is not None
    assert cmd["command"] == "quit"


def test_parse_slash_command_none():
    cmd = parse_slash_command("hello world")
    assert cmd is None


def test_parse_slash_command_empty():
    cmd = parse_slash_command("")
    assert cmd is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_screens.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement ChatScreen**

```python
# cli/tui/screens/chat.py
"""Streaming chat screen — primary interaction with Nexi."""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
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
            # Update the last Static widget with accumulated text
            nexi_static.update(f"nexi> {full_text}")

        try:
            result = await client.chat_stream(
                message,
                session_id=state.current_session_id,
                on_token=on_token,
            )
            state.current_session_id = result.get("session_id", state.current_session_id)
            state.model_name = result.get("model_used", state.model_name)
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
            # TODO: pre-fill search with args
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tui_screens.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Verify chat screen works (manual)**

Run: `python -m cli.tui.app`, type a message, verify streaming response

- [ ] **Step 6: Commit**

```bash
git add cli/tui/screens/chat.py tests/test_tui_screens.py
git commit -m "feat(tui): implement streaming chat screen with slash commands"
```

---

### Task 8: Memory recall screen

**Files:**
- Modify: `cli/tui/screens/memory.py` (replace stub)

**Interfaces:**
- Consumes: `AsyncXnchClient.memory_recall()`, `dedupe_memory_results` from `cli/util.py`
- Produces: Full memory search + results display

- [ ] **Step 1: Implement MemoryScreen**

```python
# cli/tui/screens/memory.py
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
```

- [ ] **Step 2: Verify memory screen works (manual)**

Run TUI, navigate to Memory screen, type a search query, verify results appear

- [ ] **Step 3: Commit**

```bash
git add cli/tui/screens/memory.py
git commit -m "feat(tui): implement memory recall screen"
```

---

### Task 9: Sessions management screen

**Files:**
- Modify: `cli/tui/screens/sessions.py` (replace stub)

**Interfaces:**
- Consumes: `AsyncXnchClient.new_session()`, `AsyncXnchClient.clear_session()`
- Produces: Session list with create/switch/clear

- [ ] **Step 1: Implement SessionsScreen**

```python
# cli/tui/screens/sessions.py
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
```

- [ ] **Step 2: Verify sessions screen works (manual)**

Navigate to Sessions, click New Session, verify session ID changes

- [ ] **Step 3: Commit**

```bash
git add cli/tui/screens/sessions.py
git commit -m "feat(tui): implement session management screen"
```

---

### Task 10: MCP tools browser screen

**Files:**
- Modify: `cli/tui/screens/tools.py` (replace stub)

**Interfaces:**
- Consumes: `AsyncXnchClient.mcp_tools()`, `AsyncXnchClient.mcp_call()`
- Produces: Tool list, filter, invoke, result display

- [ ] **Step 1: Implement ToolsScreen**

```python
# cli/tui/screens/tools.py
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
```

- [ ] **Step 2: Verify tools screen works (manual)**

Navigate to Tools, verify tool list loads, invoke a tool, verify result

- [ ] **Step 3: Commit**

```bash
git add cli/tui/screens/tools.py
git commit -m "feat(tui): implement MCP tools browser screen"
```

---

### Task 11: Health dashboard screen

**Files:**
- Modify: `cli/tui/screens/health.py` (replace stub)

**Interfaces:**
- Consumes: `AsyncXnchClient.health()`, `AsyncXnchClient.system_state()`, `AsyncXnchClient.nexi_health()`
- Produces: Health dashboard with polling

- [ ] **Step 1: Implement HealthScreen**

```python
# cli/tui/screens/health.py
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
    #health-refresh {
        height: 3;
        dock: bottom;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading health data...", id="health-content")
        yield Button("Refresh", id="btn-refresh", variant="primary", id="health-refresh")

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
policy:  {policy_ver}

MCP Bridge: checking..."""

            self.query_one("#health-content", Static).update(content)

            # Update app state
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
```

- [ ] **Step 2: Verify health screen works (manual)**

Navigate to Health, verify data loads, click Refresh, verify auto-refresh

- [ ] **Step 3: Commit**

```bash
git add cli/tui/screens/health.py
git commit -m "feat(tui): implement system health dashboard screen"
```

---

### Task 12: Decision pipeline view screen

**Files:**
- Modify: `cli/tui/screens/pipeline.py` (replace stub)

**Interfaces:**
- Consumes: `AsyncXnchClient` session_init (via chat endpoint)
- Produces: Pipeline inspection view

- [ ] **Step 1: Implement PipelineScreen**

```python
# cli/tui/screens/pipeline.py
"""Decision pipeline view screen — inspect session/init results."""

from __future__ import annotations

import json
import logging
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Header, TextArea, Button, DataTable
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
            id="pipeline-input",
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
```

- [ ] **Step 2: Commit**

```bash
git add cli/tui/screens/pipeline.py
git commit -m "feat(tui): implement decision pipeline view screen"
```

---

### Task 13: Register TUI subcommand in existing CLI

**Files:**
- Modify: `cli/main.py`
- Create: `cli/tui/__main__.py`

**Interfaces:**
- Consumes: `XnchTuiApp`
- Produces: `xnch-cli tui` command

- [ ] **Step 1: Add tui subcommand to cli/main.py**

Add to `cli/main.py` after existing app definitions:

```python
# Add after line 33 (app.add_typer(voice_app, name="voice")):
@app.command()
def tui() -> None:
    """Launch the Textual TUI dashboard."""
    from cli.tui.app import XnchTuiApp
    app_tui = XnchTuiApp()
    app_tui.run()
```

- [ ] **Step 2: Create __main__.py for python -m cli.tui**

```python
# cli/tui/__main__.py
"""Allow running as: python -m cli.tui"""

from cli.tui.app import XnchTuiApp

def main() -> None:
    app = XnchTuiApp()
    app.run()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify both entry points work (manual)**

Run: `xnch-cli tui` and `python -m cli.tui`
Expected: TUI launches

- [ ] **Step 4: Commit**

```bash
git add cli/main.py cli/tui/__main__.py
git commit -m "feat(tui): register tui subcommand in CLI and add __main__.py"
```

---

### Task 14: Voice I/O mode

**Files:**
- Modify: `cli/tui/screens/chat.py` (add voice toggle)

**Interfaces:**
- Consumes: `AsyncXnchClient` voice endpoints (wrap existing `XnchCliClient.voice_*`)
- Produces: Push-to-talk voice mode in chat

- [ ] **Step 1: Add voice methods to AsyncXnchClient**

Add to `cli/tui/client.py`:

```python
    async def voice_transcribe(self, wav_bytes: bytes) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync.voice_transcribe, wav_bytes)

    async def voice_speak(self, text: str) -> bytes:
        return await asyncio.to_thread(self._sync.voice_speak, text)

    async def voice_chat(
        self, wav_bytes: bytes, *, session_id: str | None = None,
        actor_role: str | None = None, return_audio: bool = True,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.voice_chat, wav_bytes,
            session_id=session_id, actor_role=actor_role, return_audio=return_audio,
        )
```

- [ ] **Step 2: Add voice mode toggle to ChatScreen**

Add a `_voice_mode: bool = False` flag and a `/voice` command handler that:
1. Sets `_voice_mode = True`
2. Shows "Voice mode ON — press Enter to record, Escape to stop"
3. On Enter: records audio via `sounddevice`, transcribes via `/nexi/voice/transcribe`
4. Sends transcript as chat message
5. Plays back audio response via `afplay`

```python
# In ChatScreen, add to __init__:
    self._voice_mode = False

# In _handle_command, update the voice case:
    elif command == "voice":
        self._voice_mode = not self._voice_mode
        mode = "ON" if self._voice_mode else "OFF"
        self._append_message("system", f"Voice mode {mode}")
```

- [ ] **Step 3: Commit**

```bash
git add cli/tui/client.py cli/tui/screens/chat.py
git commit -m "feat(tui): add voice I/O mode to chat screen"
```

---

### Task 15: Integration tests and polish

**Files:**
- Create: `tests/test_tui_integration.py`
- Modify: various (fix edge cases)

**Interfaces:**
- Consumes: all previous tasks
- Produces: Passing integration tests, clean UX

- [ ] **Step 1: Write integration test for app launch**

```python
# tests/test_tui_integration.py
"""Integration tests for the TUI app."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from cli.tui.app import XnchTuiApp


async def test_app_instantiation():
    app = XnchTuiApp()
    assert app is not None
    assert app.state is not None
    assert app.client is not None


async def test_state_initialization():
    from cli.tui.state import TuiState
    state = TuiState()
    assert state.current_screen == "chat"
    assert state.connected is False
```

- [ ] **Step 2: Run all TUI tests**

Run: `pytest tests/test_tui_*.py -v`
Expected: All tests PASS

- [ ] **Step 3: Verify full TUI workflow (manual)**

1. Launch TUI
2. Chat with Nexi (verify streaming)
3. Navigate to Memory, search, verify results
4. Navigate to Sessions, create new session
5. Navigate to Tools, list and invoke a tool
6. Navigate to Health, verify status
7. Navigate to Pipeline, run test input
8. Test paste (paste multi-line text into chat input)
9. Test keybindings (Ctrl+Q, Ctrl+N, etc.)

- [ ] **Step 4: Commit**

```bash
git add tests/test_tui_integration.py
git commit -m "feat(tui): add integration tests and polish"
```

---

## Spec Coverage Check

| Spec Section | Task |
|---|---|
| Entry point / package structure | Task 1, 13 |
| Async client adapter | Task 2 |
| Reactive state model | Task 3 |
| TUI config | Task 4 |
| App shell + layout | Task 5 |
| Sidebar widget | Task 5 |
| Status bar widget | Task 5 |
| Streaming markdown widget | Task 6 |
| Chat screen (streaming, paste, slash commands) | Task 7 |
| Memory recall screen | Task 8 |
| Sessions management screen | Task 9 |
| MCP tools browser screen | Task 10 |
| Health dashboard screen | Task 11 |
| Decision pipeline view screen | Task 12 |
| Voice I/O | Task 14 |
| CLI integration | Task 13 |
| Tests | Tasks 1,2,3,5,7,15 |

No gaps found. All spec sections are covered.
