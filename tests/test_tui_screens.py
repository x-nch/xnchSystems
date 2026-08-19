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


def test_parse_slash_command_session_list():
    cmd = parse_slash_command("/session list")
    assert cmd is not None
    assert cmd["command"] == "session"
    assert cmd["args"] == "list"


def test_parse_slash_command_health():
    cmd = parse_slash_command("/health")
    assert cmd is not None
    assert cmd["command"] == "health"
    assert cmd["args"] == ""


def test_parse_slash_command_tools():
    cmd = parse_slash_command("/tools")
    assert cmd is not None
    assert cmd["command"] == "tools"
    assert cmd["args"] == ""


def test_parse_slash_command_recall_no_args():
    cmd = parse_slash_command("/recall")
    assert cmd is not None
    assert cmd["command"] == "recall"
    assert cmd["args"] == ""


def test_parse_slash_command_voice():
    cmd = parse_slash_command("/voice")
    assert cmd is not None
    assert cmd["command"] == "voice"
    assert cmd["args"] == ""


def test_parse_slash_command_json():
    cmd = parse_slash_command("/json")
    assert cmd is not None
    assert cmd["command"] == "json"
    assert cmd["args"] == ""
