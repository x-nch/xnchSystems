"""Actor context passed to MCP tool handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from xnch.security.trust_model import TrustLevel, get_trust_level


@dataclass
class ActorContext:
    actor_role: str
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str | None = None

    @property
    def trust_level(self) -> TrustLevel:
        return get_trust_level(self.actor_role)
