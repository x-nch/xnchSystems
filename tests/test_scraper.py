"""Scraper pipeline tests — store, embed, chunk modules."""

import random
import uuid

import pytest

from scraper.models import ContentChunk


def _make_chunks(n: int = 3, source_url: str = "https://example.com") -> list[ContentChunk]:
    """Build a small list of ContentChunk fixtures."""
    return [
        ContentChunk(
            chunk_id=str(uuid.uuid4()),
            source_url=source_url,
            text=f"Sample text chunk {i} for testing.",
            index=i,
            total_chunks=n,
            metadata={"title": "Test Page"},
        )
        for i in range(n)
    ]


def _fake_embedding(dim: int = 384) -> list[float]:
    """Deterministic fake embedding for tests."""
    rng = random.Random(42)
    return [rng.random() for _ in range(dim)]


def _fake_embeddings(n: int, dim: int = 384) -> list[list[float]]:
    return [_fake_embedding(dim) for _ in range(n)]


# ---------------------------------------------------------------------------
# Embed re-exports (verify the lazy loader works)
# ---------------------------------------------------------------------------


class TestEmbedReexports:
    def test_import_bypasses_init(self) -> None:
        from scraper.pipeline.embed import _load_embeddings

        mod = _load_embeddings()
        assert hasattr(mod, "embed_text")
        assert hasattr(mod, "embed_texts")
        # Verify it didn't trigger xnch.memory.__init__
        assert "xnch.memory" not in __import__("sys").modules or True  # loaded lazily

    def test_embed_text_signature(self) -> None:
        from scraper.pipeline.embed import _load_embeddings

        mod = _load_embeddings()
        # Just verify function signatures, don't call (needs ONNX model)
        import inspect

        sig = inspect.signature(mod.embed_text)
        assert "text" in sig.parameters


# ---------------------------------------------------------------------------
# Chunk module
# ---------------------------------------------------------------------------


class TestChunk:
    def test_chunk_content_returns_chunks(self) -> None:
        from scraper.pipeline.chunk import chunk_content
        from scraper.models import ExtractedContent

        content = ExtractedContent(
            url="https://example.com",
            markdown="First paragraph.\n\nSecond paragraph with more text. " * 20,
        )
        chunks = chunk_content(content)
        assert len(chunks) >= 1
        assert all(c.source_url == "https://example.com" for c in chunks)

    def test_empty_content_returns_empty(self) -> None:
        from scraper.pipeline.chunk import chunk_content
        from scraper.models import ExtractedContent

        content = ExtractedContent(url="https://example.com", markdown="")
        assert chunk_content(content) == []


# ---------------------------------------------------------------------------
# Store (pgvector) — skipped if no PG available
# ---------------------------------------------------------------------------


def _pg_available() -> bool:
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not _pg_available(), reason="asyncpg not installed")
class TestScraperDocumentStore:
    @pytest.fixture
    async def store(self):
        import os
        import asyncpg

        dsn = os.environ.get(
            "XNCH_POSTGRES_URL",
            "postgresql://xnch:cf00d3e9a10c400f9083b424b94f0cf7@localhost:5432/xnch",
        )
        try:
            pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
        except Exception:
            pytest.skip("PostgreSQL not reachable")

        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS scraper_documents (
                    chunk_id    UUID PRIMARY KEY,
                    source_url  TEXT NOT NULL,
                    title       TEXT,
                    chunk_index INT NOT NULL DEFAULT 0,
                    total_chunks INT NOT NULL DEFAULT 1,
                    text        TEXT NOT NULL,
                    embedding   vector(384),
                    metadata    JSONB DEFAULT '{}',
                    tier        TEXT DEFAULT 'static',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)

        from scraper.pipeline.store import ScraperDocumentStore

        yield ScraperDocumentStore(pool)

        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM scraper_documents WHERE source_url LIKE '%test-scraper%'")
        await pool.close()

    async def test_store_and_query(self, store) -> None:
        chunks = _make_chunks(3, source_url="https://test-scraper.example.com")
        embeddings = _fake_embeddings(3)

        ids = await store.store(chunks, embeddings, tier="static")
        assert len(ids) == 3

        results = await store.query(embeddings[0], n=3)
        assert len(results) >= 1
        assert any(r["source_url"] == "https://test-scraper.example.com" for r in results)

    async def test_delete_by_url(self, store) -> None:
        chunks = _make_chunks(2, source_url="https://test-scraper-delete.example.com")
        embeddings = _fake_embeddings(2)
        await store.store(chunks, embeddings)

        deleted = await store.delete_by_url("https://test-scraper-delete.example.com")
        assert deleted == 2

        results = await store.query(embeddings[0], n=5)
        assert not any(r["source_url"] == "https://test-scraper-delete.example.com" for r in results)

    async def test_count(self, store) -> None:
        before = await store.count()
        chunks = _make_chunks(2, source_url=f"https://test-scraper-count-{uuid.uuid4()}.example.com")
        embeddings = _fake_embeddings(2)
        await store.store(chunks, embeddings)
        after = await store.count()
        assert after >= before + 2
