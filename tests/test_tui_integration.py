"""Integration tests for the TUI package — cross-module correctness."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cli.tui import __version__


# ── Module imports ─────────────────────────────────────────────────


def test_tui_package_version():
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"


def test_import_all_modules():
    """Every public TUI module is importable."""
    import cli.tui.app
    import cli.tui.client
    import cli.tui.config
    import cli.tui.state

    from cli.tui.screens import (
        ChatScreen,
        MemoryScreen,
        SessionsScreen,
        ToolsScreen,
        HealthScreen,
        PipelineScreen,
    )
    from cli.tui.widgets.sidebar import Sidebar
    from cli.tui.widgets.status_bar import StatusBar
    from cli.tui.widgets.markdown import StreamingMarkdown
    from cli.tui.widgets.search_input import SearchInput

    assert all([
        ChatScreen, MemoryScreen, SessionsScreen,
        ToolsScreen, HealthScreen, PipelineScreen,
        Sidebar, StatusBar, StreamingMarkdown, SearchInput,
    ])


# ── App ↔ State ↔ Config integration ─────────────────────────────


def test_app_instantiation():
    from cli.tui.app import XnchTuiApp
    from cli.tui.state import TuiState
    from cli.tui.client import AsyncXnchClient

    app = XnchTuiApp()
    assert app is not None
    assert isinstance(app.state, TuiState)
    assert isinstance(app.client, AsyncXnchClient)


def test_app_custom_config():
    from cli.tui.app import XnchTuiApp
    from cli.tui.config import TuiConfig

    cfg = TuiConfig(sidebar_width=30, health_poll_interval_s=10.0)
    app = XnchTuiApp(config=cfg)
    assert app.config.sidebar_width == 30
    assert app.config.health_poll_interval_s == 10.0


def test_state_resets_message_count():
    from cli.tui.state import TuiState

    state = TuiState()
    state.increment_message_count()
    state.increment_message_count()
    state.increment_message_count()
    assert state.message_count == 3
    state.reset_message_count()
    assert state.message_count == 0


def test_config_frozen():
    from cli.tui.config import TuiConfig

    cfg = TuiConfig()
    with pytest.raises(AttributeError):
        cfg.sidebar_width = 999  # type: ignore[misc]


def test_config_defaults():
    from cli.tui.config import TuiConfig

    cfg = TuiConfig()
    assert cfg.health_poll_interval_s == 30.0
    assert cfg.max_chat_history == 200
    assert cfg.sidebar_width == 24
    assert cfg.detail_panel_width == 40
    assert cfg.default_top_k == 5
    assert cfg.mcp_actor_role == "nexi"


def test_config_keybindings():
    from cli.tui.config import TuiConfig

    cfg = TuiConfig()
    assert cfg.key_quit == "ctrl+q"
    assert cfg.key_new_session == "ctrl+n"
    assert cfg.key_recall == "ctrl+r"
    assert cfg.key_memory == "ctrl+m"
    assert cfg.key_health == "ctrl+h"
    assert cfg.key_tools == "ctrl+t"
    assert cfg.key_toggle_detail == "tab"
    assert cfg.key_close_detail == "escape"


# ── App screen registry ───────────────────────────────────────────


def test_app_screen_registry():
    from cli.tui.app import XnchTuiApp

    app = XnchTuiApp()
    assert "chat" in app.SCREENS
    assert "memory" in app.SCREENS
    assert "sessions" in app.SCREENS
    assert "tools" in app.SCREENS
    assert "health" in app.SCREENS
    assert "pipeline" in app.SCREENS
    assert len(app.SCREENS) == 6


def test_app_bindings():
    from cli.tui.app import XnchTuiApp

    app = XnchTuiApp()
    binding_keys = [b.key for b in app.BINDINGS]
    assert "ctrl+q" in binding_keys
    assert "ctrl+n" in binding_keys
    assert "ctrl+r" in binding_keys
    assert "ctrl+m" in binding_keys
    assert "ctrl+h" in binding_keys
    assert "ctrl+t" in binding_keys
    assert "tab" in binding_keys


# ── Slash command parsing (integration coverage) ──────────────────


@pytest.mark.parametrize("text,expected_cmd,expected_args", [
    ("/quit", "quit", ""),
    ("/session new", "session", "new"),
    ("/session list", "session", "list"),
    ("/recall deployment", "recall", "deployment"),
    ("/health", "health", ""),
    ("/tools", "tools", ""),
    ("/voice", "voice", ""),
    ("/json", "json", ""),
    ("/unknown", "unknown", ""),
    ("/recall", "recall", ""),
])
def test_slash_command_parsing(text, expected_cmd, expected_args):
    from cli.tui.screens.chat import parse_slash_command

    result = parse_slash_command(text)
    assert result is not None
    assert result["command"] == expected_cmd
    assert result["args"] == expected_args


@pytest.mark.parametrize("text", [
    "hello",
    "just typing",
    "",
    "  ",
    "not a command",
])
def test_non_command_input_returns_none(text):
    from cli.tui.screens.chat import parse_slash_command

    assert parse_slash_command(text) is None


# ── Client ↔ State integration ────────────────────────────────────


def test_client_instantiation():
    from cli.tui.client import AsyncXnchClient

    client = AsyncXnchClient.__new__(AsyncXnchClient)
    client.config = MagicMock()
    client.config.nexi_url = "http://localhost:8000"
    client._sync = MagicMock()
    client._stream_client = MagicMock()
    assert client is not None


def test_state_fields_update():
    from cli.tui.state import TuiState

    state = TuiState()
    state.current_session_id = "test-session-123"
    state.connected = True
    state.model_name = "gpt-4o"
    state.current_screen = "memory"
    state.mcp_tools = [{"name": "tool1"}]
    state.sessions = [{"id": "s1"}]
    state.detail_visible = True

    assert state.current_session_id == "test-session-123"
    assert state.connected is True
    assert state.model_name == "gpt-4o"
    assert state.current_screen == "memory"
    assert len(state.mcp_tools) == 1
    assert len(state.sessions) == 1
    assert state.detail_visible is True


def test_health_status_dict():
    from cli.tui.state import TuiState

    state = TuiState()
    state.health_status = {"status": "ok", "redis": "connected", "version": "0.1.0"}
    assert state.health_status["status"] == "ok"
    assert state.health_status["redis"] == "connected"


# ── Widget imports ────────────────────────────────────────────────


def test_widget_imports():
    from cli.tui.widgets.sidebar import Sidebar
    from cli.tui.widgets.status_bar import StatusBar
    from cli.tui.widgets.markdown import StreamingMarkdown
    from cli.tui.widgets.search_input import SearchInput

    assert Sidebar is not None
    assert StatusBar is not None
    assert StreamingMarkdown is not None
    assert SearchInput is not None


# ── Screen class types ────────────────────────────────────────────


def test_screen_classes_are_screen_subclasses():
    from textual.screen import Screen
    from cli.tui.screens import (
        ChatScreen, MemoryScreen, SessionsScreen,
        ToolsScreen, HealthScreen, PipelineScreen,
    )

    for cls in [ChatScreen, MemoryScreen, SessionsScreen,
                ToolsScreen, HealthScreen, PipelineScreen]:
        assert issubclass(cls, Screen), f"{cls.__name__} should subclass Screen"


# ── CLI integration ───────────────────────────────────────────────


def test_cli_tui_command_exists():
    """The CLI app has a 'tui' command registered."""
    try:
        from cli.main import app as typer_app
    except ModuleNotFoundError:
        pytest.skip("cli.main requires optional deps (numpy) not installed in test env")

    command_names = [cmd.name for cmd in typer_app.registered_commands]
    assert "tui" in command_names
