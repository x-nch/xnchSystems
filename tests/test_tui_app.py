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
