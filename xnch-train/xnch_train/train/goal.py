"""Thin xnch Goal + HITL client for training cycles (reuses existing plumbing).

Synchronous HTTP client to the xnch control-plane Goal REST API and the
standard verdict/HITL path. Used by the cycle orchestrator (Task 6). Talks to
xnch over HTTP only — no cross-package Python import of xnch.
"""
from __future__ import annotations

import httpx


class GoalClient:
    """Synchronous client for xnch Goal claim + promotion proposal emission."""

    def __init__(
        self,
        base_url: str,
        token: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._c = httpx.Client(
            base_url=base_url,
            headers=headers,
            transport=transport or httpx.HTTPTransport(),
        )

    def claim(self, *, objective: str, max_steps: int, lease_owner: str) -> str | None:
        """Create a Goal then claim it; return the goal id, or None if absent."""
        r = self._c.post("/goals", json={"objective": objective, "max_steps": max_steps})
        r.raise_for_status()
        gid = r.json().get("goal_id")
        if not gid:
            return None
        self._c.post("/goals/claim", json={"lease_owner": lease_owner})
        return gid

    def emit_proposal(self, proposal: dict) -> None:
        """Ride the standard verdict/HITL path.

        Proposal shape is inherited from `gate/promotion_gate.GateDecision.proposal`,
        e.g. {"type": "checkpoint.promotion", ...}.
        """
        r = self._c.post("/policy/verdict", json=proposal)
        r.raise_for_status()


def claim_goal(
    client: GoalClient,
    *,
    objective: str,
    max_steps: int,
    lease_owner: str,
) -> str | None:
    """Module-level convenience: claim a Goal and return its id (or None)."""
    return client.claim(objective=objective, max_steps=max_steps, lease_owner=lease_owner)


def emit_promotion_proposal(client: GoalClient, proposal: dict) -> None:
    """Module-level convenience: emit a checkpoint.promotion proposal via HITL."""
    client.emit_proposal(proposal)
