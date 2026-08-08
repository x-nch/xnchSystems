#!/usr/bin/env python3
"""Report potential overlap between pgvector notes and agentmemory.

Read-only audit — does not modify either store.

Usage:
  python scripts/audit-memory-overlap.py
  python scripts/audit-memory-overlap.py --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Repo root on PYTHONPATH when run from xnchSystems
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "xnch"))
sys.path.insert(0, str(_ROOT))

from xnch.config import settings  # noqa: E402
from xnch.memory.pg_episodic_store import PgEpisodicStore  # noqa: E402


async def _fetch_pg_notes(limit: int) -> list[dict]:
    store = PgEpisodicStore(settings.postgres_url)
    await store.connect()
    try:
        rows = await store.fetch_by_type("note", limit=limit)
        return rows or []
    finally:
        await store.close()


async def _fetch_am_snippets(limit: int) -> list[str]:
    import httpx

    url = "http://127.0.0.1:8001/mcp/call"
    snippets: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={"X-Actor-Role": "nexi", "Content-Type": "application/json"},
                json={
                    "name": "am_memory_recall",
                    "arguments": {"query": "deploy lesson architecture", "limit": limit},
                },
            )
            resp.raise_for_status()
            result = resp.json().get("result") or {}
            for item in result.get("results") or []:
                if isinstance(item, dict):
                    text = (item.get("content") or item.get("text") or "").strip()
                    if text:
                        snippets.append(text)
    except Exception as exc:
        print(f"agentmemory recall skipped: {exc}", file=sys.stderr)
    return snippets


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Audit pgvector vs agentmemory overlap")
    parser.add_argument("--limit", type=int, default=15, help="Max items per store")
    parser.add_argument("--threshold", type=float, default=0.65, help="Similarity flag threshold")
    args = parser.parse_args()

    notes = await _fetch_pg_notes(args.limit)
    am_texts = await _fetch_am_snippets(args.limit)

    print(f"pgvector notes (type=note): {len(notes)}")
    print(f"agentmemory snippets: {len(am_texts)}")
    print()

    flagged = 0
    for note in notes:
        content = (note.get("raw_text") or note.get("summary") or "").strip()
        if not content:
            continue
        for am in am_texts:
            score = _similarity(content, am)
            if score >= args.threshold:
                flagged += 1
                print(f"OVERLAP score={score:.2f}")
                print(f"  pg: {content[:120]}...")
                print(f"  am: {am[:120]}...")
                print()

    if flagged == 0:
        print("No high-similarity pairs found above threshold.")
    else:
        print(f"Flagged pairs: {flagged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
