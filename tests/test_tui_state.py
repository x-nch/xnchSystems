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
