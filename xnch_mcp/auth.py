"""MCP client auth and tier access control."""

from __future__ import annotations

from xnch.security.trust_model import TrustLevel, get_trust_level
from xnch_mcp.tiers import ToolTier

_MAX_TIER: dict[TrustLevel, ToolTier] = {
    TrustLevel.UNTRUSTED: ToolTier.T0_READ,
    TrustLevel.EXTERNAL_AGENT: ToolTier.T0_READ,
    TrustLevel.TRUSTED_AGENT: ToolTier.T1_WRITE,
    TrustLevel.OWNER: ToolTier.T2_EXEC,
    TrustLevel.SYSTEM: ToolTier.T2_EXEC,
}


def max_tier_for_role(actor_role: str) -> ToolTier:
    return _MAX_TIER.get(get_trust_level(actor_role), ToolTier.T0_READ)


def actor_from_env() -> str:
    import os

    return os.environ.get("XNCH_ACTOR", "external")
