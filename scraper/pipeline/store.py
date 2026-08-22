"""PostgreSQL + pgvector store for scraped documents.

Replaces the standalone ChromaDB backend. Uses the same pgvector instance
as xnch's episodic memory, storing scraped content in a dedicated
``scraper_documents`` table with MiniLM-L6-v2 (384-dim) embeddings.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import asyncpg

from ..models import ContentChunk

logger = logging.getLogger(__name__)


class ScraperDocumentStore:
    """Async vector store for scraped document chunks backed by pgvector."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def store(
        self,
        chunks: list[ContentChunk],
        embeddings: list[list[float]],
        tier: str = "static",
    ) -> list[str]:
        """Store chunks with their embeddings. Returns chunk IDs."""
        if not chunks:
            return []

        ids: list[str] = []
        async with self._pool.acquire() as conn:
            for chunk, embedding in zip(chunks, embeddings):
                chunk_id = chunk.chunk_id
                ids.append(chunk_id)
                await conn.execute(
                    """INSERT INTO scraper_documents
                         (chunk_id, source_url, title, chunk_index, total_chunks,
                          text, embedding, metadata, tier)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                       ON CONFLICT (chunk_id) DO UPDATE SET
                         text = EXCLUDED.text,
                         embedding = EXCLUDED.embedding,
                         metadata = EXCLUDED.metadata,
                         tier = EXCLUDED.tier""",
                    uuid.UUID(chunk_id),
                    chunk.source_url,
                    chunk.metadata.get("title", ""),
                    chunk.index,
                    chunk.total_chunks,
                    chunk.text,
                    _to_vector(embedding),
                    _jsonb(chunk.metadata),
                    tier,
                )
        logger.info("Stored %d chunks in scraper_documents", len(ids))
        return ids

    async def query(
        self,
        query_embedding: list[float],
        n: int = 5,
    ) -> list[dict[str, Any]]:
        """Query for similar content by embedding cosine distance.

        Returns list of dicts with id, text, source_url, metadata, similarity.
        """
        async with self._pool.acquire() as conn:
            count = await conn.fetchval("SELECT count(*) FROM scraper_documents")
            if count == 0:
                return []

            rows = await conn.fetch(
                """SELECT chunk_id, source_url, title, text, metadata, tier,
                          1 - (embedding <=> $1) AS similarity
                   FROM scraper_documents
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> $1
                   LIMIT $2""",
                _to_vector(query_embedding),
                min(n, count),
            )

        return [
            {
                "id": str(r["chunk_id"]),
                "text": r["text"],
                "source_url": r["source_url"],
                "title": r["title"],
                "metadata": r["metadata"],
                "tier": r["tier"],
                "similarity": float(r["similarity"]),
            }
            for r in rows
        ]

    async def delete_by_url(self, url: str) -> int:
        """Delete all chunks from a specific URL. Returns count deleted."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM scraper_documents WHERE source_url = $1", url
            )
        # result is like "DELETE 5"
        deleted = int(result.split()[-1]) if result else 0
        if deleted:
            logger.info("Deleted %d chunks for URL %s", deleted, url)
        return deleted

    async def count(self) -> int:
        """Return total number of stored chunks."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT count(*) FROM scraper_documents")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_vector(embedding: list[float] | None) -> str | None:
    if embedding is None:
        return None
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


def _jsonb(value: Any) -> str | None:
    import json

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)
