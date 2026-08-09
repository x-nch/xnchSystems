"""Agent CLI adapters."""

from .base import AgentAdapter, AgentRequest, AgentResult, AgentStreamChunk
from .claude import ClaudeCodeAdapter
from .cursor import CursorAgentAdapter
from .opencode import OpenCodeAdapter

__all__ = [
    "AgentAdapter",
    "AgentRequest",
    "AgentResult",
    "AgentStreamChunk",
    "ClaudeCodeAdapter",
    "OpenCodeAdapter",
    "CursorAgentAdapter",
]
