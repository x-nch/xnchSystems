"""Tool tier definitions."""

from __future__ import annotations

import enum


class ToolTier(enum.IntEnum):
    T0_READ = 0
    T1_WRITE = 1
    T2_EXEC = 2
