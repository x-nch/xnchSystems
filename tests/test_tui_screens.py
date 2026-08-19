"""Tests for TUI screens."""

from __future__ import annotations

import pytest
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
