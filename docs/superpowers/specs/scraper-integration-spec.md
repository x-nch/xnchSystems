# Spec: Scraper Integration into xnchSystems

**Status:** Approved — building  
**Date:** 2026-08-20  
**Scope:** Replace scraper's standalone ChromaDB with existing pgvector; deploy via no-k3s docker compose + systemd

---

## 1. Problem Statement

The `scraper/` module (13 files, fully built) provides 3-tier web crawling + content processing but:
- Uses a standalone **ChromaDB** database that no other component uses
- Uses **sentence-transformers** (heavy PyTorch dependency) when `xnch/memory/embeddings.py` already provides the same model via lightweight ONNX
- Is **not deployable**: Dockerfiles don't copy `scraper/`, deps missing from `xnch/pyproject.toml`
- Config is isolated in `scraper/config.py` instead of the central `xnch/config.py`

## 2. Current State

### What exists
| Component | Status | Location |
|-----------|--------|----------|
| Scraper tiers (static/browser/social) | Complete | `scraper/tiers/` |
| Pipeline (chunk, embed, store) | Complete but ChromaDB-coupled | `scraper/pipeline/` |
| API layer | Complete but sync | `scraper/api.py` |
| MCP handlers (6 tools) | Complete, registered | `xnch_mcp/handlers/scraper.py` |
| pgvector store | Production-ready | `xnch/memory/pg_episodic_store.py` |
| ONNX embedder | Production-ready | `xnch/memory/embeddings.py` |

### What's broken
- `scraper/pipeline/store.py` imports `chromadb` — fails if not installed
- `scraper/pipeline/embed.py` imports `sentence_transformers` — heavy, duplicates ONNX embedder
- `infra/docker/xnch.Dockerfile` only copies `xnch/` subdirectory — scraper at root level is excluded
- `infra/docker/nexi.Dockerfile` only copies `nexi/` — same issue if nexi calls scraper
- Scraper deps (`trafilatura`, `markdownify`, `crawlee`, `playwright`, `beautifulsoup4`) not in `xnch/pyproject.toml`

### Deployment topology (no-k3s)
- **Node A** (192.168.50.1): docker compose (redis, postgres-pgvector, litellm, langfuse, searxng) + systemd (`xnch.service`)
- **Node B** (192.168.50.2): systemd (`vllm-ornith`, `nexi.service`)
- Both run as user `x-nch`, working dir `/home/x-nch/xnchSystems`
- `xnch.service` runs: `.venv/bin/uvicorn xnch.main:app --host 0.0.0.0 --port 8001`

## 3. Design Decisions

### 3.1 Replace ChromaDB with pgvector

**Decision:** Rewrite `scraper/pipeline/store.py` to use the existing `PgEpisodicStore` pool against a new `scraper_documents` table.

**Rationale:**
- No new database to deploy, monitor, or back up
- Scraped content becomes queryable alongside episodic memory (unified vector search)
- Eliminates `chromadb` dependency (~200MB)
- The existing pgvector container already runs on Node A with the same `all-MiniLM-L6-v2` 384-dim vectors

**Trade-off:** Current scraper API functions (`crawl_and_store`, `query_similar`) are sync. The pgvector store is async (`asyncpg`). MCP handlers already run async, so the tool layer works. The `scraper/api.py` sync functions either:
- (a) Get async variants, or
- (b) Are deprecated in favor of MCP handlers doing the DB calls directly

**Recommendation:** Option (b) — the MCP handlers are the real entry point. `scraper/api.py` becomes a thin async wrapper over the tiers + chunking, without DB coupling.

### 3.2 Reuse xnch/memory/embeddings.py

**Decision:** Replace `scraper/pipeline/embed.py` with a thin re-export of `xnch.memory.embeddings`.

**Rationale:**
- Same model, same 384-dim output, same L2 normalization
- Eliminates `sentence-transformers` + PyTorch (~2GB)
- ONNX runtime is already a dependency

### 3.3 Config merge

**Decision:** Move scraper-specific env vars into `xnch/config.py` under `ScraperSettings`.

**Rationale:** Single source of truth for all system config. The `xnch/config.py` already uses `pydantic-settings` with `env_prefix`.

## 4. Schema Changes

New table added to `_SCHEMA` in `pg_episodic_store.py`:

```sql
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
);
CREATE INDEX IF NOT EXISTS idx_scraper_docs_url ON scraper_documents(source_url);
CREATE INDEX IF NOT EXISTS idx_scraper_docs_embedding ON scraper_documents
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**IVFFlat index:** Lists=100 is appropriate for <1M rows. Rebuild if corpus grows significantly.

## 5. Module Changes

### 5.1 `scraper/pipeline/store.py` — REWRITE

Replace ChromaDB operations with asyncpg against `scraper_documents`:

| Current | New |
|---------|-----|
| `get_collection()` | Uses `PgEpisodicStore` pool |
| `store_chunks(chunks, embeddings)` | `async store_chunks(pool, chunks, embeddings)` → INSERT INTO scraper_documents |
| `query_similar(embedding, n)` | `async query_similar(pool, embedding, n)` → SELECT ... ORDER BY embedding <=> $1 |
| `delete_by_url(url)` | `async delete_by_url(pool, url)` → DELETE FROM scraper_documents WHERE source_url = $1 |

The module gets a `ScraperDocumentStore` class wrapping the pool:

```python
class ScraperDocumentStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def store(self, chunks: list[ContentChunk], embeddings: list[list[float]], tier: str = "static") -> list[str]: ...
    async def query(self, query_embedding: list[float], n: int = 5) -> list[dict]: ...
    async def delete_by_url(self, url: str) -> int: ...
    async def count(self) -> int: ...
```

### 5.2 `scraper/pipeline/embed.py` — REPLACE

Replace with re-exports from `xnch.memory.embeddings`:

```python
from xnch.memory.embeddings import embed_text as get_embedding, embed_texts as get_embeddings
```

Delete the `sentence_transformers` import and `_model_cache` cache.

### 5.3 `scraper/api.py` — SIMPLIFY

Remove sync DB operations. The API layer becomes:

```python
async def crawl(url, tier="auto", headless=True) -> ExtractedContent: ...  # unchanged
async def crawl_batch(urls, tier="auto", max_concurrent=5) -> list[ExtractedContent]: ...  # unchanged

# NEW: async store via injected pool
async def crawl_and_store(urls, store: ScraperDocumentStore, tier="auto") -> list[str]: ...
```

`crawl_and_store` takes a `ScraperDocumentStore` instead of importing ChromaDB directly. This keeps the tiers decoupled from storage.

### 5.4 `xnch/config.py` — EXTEND

Add `ScraperSettings`:

```python
class ScraperSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPER_")
    default_tier: str = "auto"
    max_concurrent: int = 5
    request_timeout: float = 30.0
    instagram_session: str | None = None
    twitter_username: str | None = None
    twitter_password: str | None = None
    twitter_email: str | None = None
```

Access via `settings.scraper.default_tier`, etc.

### 5.5 `xnch_mcp/handlers/scraper.py` — UPDATE HANDLERS

The 6 handlers currently import from `scraper.pipeline.store` (ChromaDB). Update to:

1. Import `ScraperDocumentStore` from `scraper.pipeline.store`
2. Get pool from `app.pg_episodic._pool` (already initialized at xnch startup)
3. Instantiate `ScraperDocumentStore(pool)` once at module level or via `app.scraped_store`
4. Handlers become fully async DB operations

**Key handler changes:**

| Handler | Current | New |
|---------|---------|-----|
| `xnch_scraper_store` | Calls `store_chunks()` (sync ChromaDB) | `await store.store(chunks, embeddings)` |
| `xnch_scraper_query` | Calls `query_similar()` (sync ChromaDB) | `await store.query(embedding, n)` |
| `xnch_scraper_delete` | Calls `delete_by_url()` (sync ChromaDB) | `await store.delete_by_url(url)` |

### 5.6 `xnch/main.py` — INITIALIZE STORE

Add `scraper_document_store` to the app lifespan, alongside the existing `pg_episodic`:

```python
# In lifespan, after pg_episodic.connect():
app.scraped_store = ScraperDocumentStore(app.pg_episodic._pool)
```

### 5.7 `scraper/models.py` — NO CHANGES

All Pydantic models are storage-agnostic. `ContentChunk`, `ExtractedContent`, etc. remain as-is.

## 6. Dependency Changes

### Remove from root `pyproject.toml`
- `chromadb`
- `sentence-transformers` (and its transitive `torch`, `transformers`, etc.)

### Add to `xnch/pyproject.toml`
- `trafilatura` — article extraction
- `markdownify` — HTML→markdown fallback
- `beautifulsoup4` — HTML parsing (already transitive via trafilatura, but explicit)
- `crawlee` — browser-tier crawling
- `playwright` — browser engine (crawlee dependency)

### Already present
- `httpx` — static tier HTTP client
- `asyncpg` — pgvector store
- `numpy` — ONNX embeddings
- `onnxruntime` — ONNX runtime
- `tokenizers` — ONNX tokenizer

### Note on playwright
Playwright requires browser binaries (`playwright install chromium`). This must happen in the Dockerfile. The `crawlee` library handles this, but the Dockerfile needs a post-install step.

## 7. Deployment Changes

### 7.1 `infra/docker/xnch.Dockerfile`

Current:
```dockerfile
COPY xnch/ ./xnch/
```

New:
```dockerfile
COPY xnch/ ./xnch/
COPY scraper/ ./scraper/
```

Plus post-install:
```dockerfile
RUN uv sync --frozen && uv run playwright install chromium --with-deps
```

### 7.2 `xnch.service` — NO CHANGES

The service already runs from `xnchSystems/` working directory with the xnch venv. Since `scraper/` is now inside the repo and the venv has the deps, it should work as-is.

The `PYTHONPATH` is set to `/home/x-nch/xnchSystems/xnch`. The scraper module uses relative imports (`from ..models import ...`), so it needs to be importable. Add to PYTHONPATH:

```
Environment=PYTHONPATH=/home/x-nch/xnchSystems/xnch:/home/x-nch/xnchSystems
```

### 7.3 `start-node-a.sh` — NO CHANGES

Docker compose already handles postgres-pgvector. The scraper tables are created idempotently by `PgEpisodicStore.connect()`.

### 7.4 `docker-compose.yml` — NO CHANGES

The existing `postgres-pgvector` container already supports the scraper's new table. No new services needed.

## 8. Migration Plan

### Phase 1: Schema + Store (no breaking changes)
1. Add `scraper_documents` table to `_SCHEMA` in `pg_episodic_store.py`
2. Create `ScraperDocumentStore` class in `scraper/pipeline/store.py`
3. Keep old ChromaDB functions as deprecated wrappers (callers get warnings)

### Phase 2: Embedder Swap
1. Replace `scraper/pipeline/embed.py` body with re-exports from `xnch.memory.embeddings`
2. Delete `sentence_transformers` import and `_model_cache`

### Phase 3: Handler Update
1. Update `xnch_mcp/handlers/scraper.py` to use `ScraperDocumentStore`
2. Add `app.scraped_store` to xnch lifespan
3. Remove old ChromaDB imports from handlers

### Phase 4: Config + Cleanup
1. Add `ScraperSettings` to `xnch/config.py`
2. Remove `scraper/config.py` (or redirect to `xnch/config.py`)
3. Delete deprecated ChromaDB wrapper functions
4. Remove `chromadb` and `sentence-transformers` from `pyproject.toml`

### Phase 5: Deployment
1. Update `xnch.Dockerfile` to copy `scraper/` and install deps
2. Update `xnch.service` PYTHONPATH
3. Test on Node A

## 9. E2E Test Plan

### 9.1 Unit tests (`scraper/tests/`)

| Test | What it verifies |
|------|-----------------|
| `test_store.py::test_store_and_query` | Store chunks → query by embedding → verify results |
| `test_store.py::test_delete_by_url` | Store → delete → verify gone |
| `test_store.py::test_count` | Count reflects actual stored chunks |
| `test_embed.py::test_embedding_compatibility` | `xnch.memory.embeddings.embed_text` produces 384-dim vectors |
| `test_chunk.py::test_chunk_content` | Chunker produces valid ContentChunk list |
| `test_tiers.py::test_crawl_static` | Static tier fetches and extracts content |

### 9.2 MCP handler tests (`xnch/tests/test_scraper_handlers.py`)

| Test | What it verifies |
|------|-----------------|
| `test_xnch_scraper_store` | Store tool: crawl URL → store → return chunk count |
| `test_xnch_scraper_query` | Query tool: store known content → query → verify match |
| `test_xnch_scraper_delete` | Delete tool: store → delete → verify gone |
| `test_xnch_scraper_crawl` | Crawl tool: fetch URL → return markdown content |
| `test_xnch_scraper_batch` | Batch tool: crawl multiple URLs |
| `test_xnch_scraper_social` | Social tool: detect platform → return result |

### 9.3 Integration test (`tests/test_scraper_e2e.py`)

Full pipeline: crawl → chunk → embed → store → query → delete

### 9.4 E2E smoke test update (`infra/no-k3s/e2e-test.sh`)

Add scraper tool tests after existing pipeline tests.

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| IVFFlat index rebuild on large corpus | Slow queries after 100K+ chunks | Monitor row count; rebuild index periodically; consider HNSW for >500K rows |
| Playwright binary size in Docker image | +500MB image | Multi-stage build; install chromium only in scraper stage |
| Sync→async migration breaks callers | Runtime errors | Deprecation wrappers in Phase 1; grep for all `store_chunks`/`query_similar` callers before removing |
| Social crawlers need env vars | Instagram/Twitter fail silently | Document required env vars in `.env.example`; add startup validation in `ScraperSettings` |
| Scraper table competes with episodes for pgvector index | Slower episode queries | Separate indexes (different tables); IVFFlat lists partitioned by table |
