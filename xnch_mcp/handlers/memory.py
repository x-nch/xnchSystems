"""T0/T1 memory tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xnch.security.memory_guard import validate_memory_write
from xnch.security.trust_model import get_trust_level
from xnch_mcp.context import ActorContext
from xnch_mcp.registry import ToolDef
from xnch_mcp.tiers import ToolTier

_POLICY: Any = None


def _routing_policy() -> Any:
    global _POLICY
    if _POLICY is None:
        from xnch.config import settings
        from xnch.memory.routing_policy import load_memory_routing_policy

        _POLICY = load_memory_routing_policy(Path(settings.memory_routing_policy_path))
    return _POLICY


async def _memory_recall(app: Any, _actor: ActorContext, args: dict[str, Any]) -> list[dict[str, Any]]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")
    top_k = int(args.get("top_k", 5))
    episodes = await app.pg_episodic.retrieve_similar(query_text=query, top_k=top_k)
    results: list[dict[str, Any]] = []
    for ep in episodes:
        results.append({
            "id": ep.get("id"),
            "type": ep.get("type", "episode"),
            "timestamp": ep.get("timestamp"),
            "content": ep.get("raw_text") or ep.get("summary", ""),
            "similarity": ep.get("similarity", 0.0),
            "importance": ep.get("importance", 0.0),
        })
    return results


async def _memory_surface(app: Any, _actor: ActorContext, _args: dict[str, Any]) -> list[dict[str, Any]]:
    if not hasattr(app, "_nexi_proactivity"):
        from nexi.proactivity.engine import ProactivityEngine

        redis = app.kv_cache.redis_client
        app._nexi_proactivity = ProactivityEngine(redis)
    events = await app._nexi_proactivity.get_pending()
    return [e.to_dict() for e in events]


async def _memory_store_note(app: Any, actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    policy = _routing_policy()
    if actor.actor_role in policy.deprecate_store_note_for:
        raise PermissionError(
            f"actor '{actor.actor_role}' cannot use xnch_memory_store_note — "
            "use am_memory_save or am_memory_lesson_save for curated facts"
        )

    text = str(args.get("text", "")).strip()
    if not text:
        raise ValueError("text is required")
    validation = validate_memory_write(
        content=text,
        actor_role=actor.actor_role,
        trust_level=get_trust_level(actor.actor_role),
    )
    if not validation[0]:
        raise PermissionError(validation[1] or "Memory write blocked")
    episode_id = await app.pg_episodic.store_episode(
        type_="note",
        raw_text=text,
        summary=text[:120],
        session_id=actor.session_id,
    )
    return {"status": "ok", "episode_id": episode_id}


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_memory_recall",
        description=(
            "Semantic search over episodic chat memory (pgvector). Auto-injected into Nexi "
            "context each turn. Use for conversation continuity and 'what did we discuss?' — "
            "not for deploy runbooks (use am_memory_lesson_recall)."
        ),
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "description": "Max results", "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_memory_recall,
    ),
    ToolDef(
        name="xnch_memory_surface",
        description="List pending proactivity events.",
        tier=ToolTier.T0_READ,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_memory_surface,
    ),
    ToolDef(
        name="xnch_memory_store_note",
        description=(
            "Store a short note in pgvector episodic memory. Deprecated for nexi — use "
            "am_memory_save or am_memory_lesson_save for curated cross-session facts. "
            "Reserved for operator/opencode explicit pgvector notes."
        ),
        tier=ToolTier.T1_WRITE,
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Note content"},
                "session_id": {"type": "string", "description": "Optional session id"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        handler=_memory_store_note,
    ),
]
