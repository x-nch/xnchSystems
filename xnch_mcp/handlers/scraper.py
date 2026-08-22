"""T0/T1 web scraping tools — tiered crawling, social media, and RAG pipeline."""

from __future__ import annotations

import logging
from typing import Any

from xnch_mcp.context import ActorContext
from xnch_mcp.tool_def import ToolDef
from xnch_mcp.tiers import ToolTier

logger = logging.getLogger(__name__)

_SCRAPER_ACTORS = frozenset({"nexi", "operator", "opencode"})


async def _scraper_crawl(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    from scraper.api import crawl

    url = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("url is required")

    tier = args.get("tier", "auto")
    result = await crawl(url, tier=tier)
    return {
        "title": result.title,
        "url": result.url,
        "markdown": result.markdown,
        "language": result.language,
        "word_count": len(result.markdown.split()),
        "metadata": result.metadata,
    }


async def _scraper_batch(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    from scraper.api import crawl_batch

    urls = args.get("urls", [])
    if not urls:
        raise ValueError("urls is required (non-empty array)")

    tier = args.get("tier", "auto")
    results = await crawl_batch(urls, tier=tier)
    return {
        "count": len(results),
        "results": [
            {
                "title": r.title,
                "url": r.url,
                "word_count": len(r.markdown.split()),
                "markdown": r.markdown,
            }
            for r in results
        ],
    }


async def _scraper_social(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    platform = str(args.get("platform", "")).strip().lower()
    username = str(args.get("username", "")).strip()
    if not platform:
        raise ValueError("platform is required")
    if not username:
        raise ValueError("username is required")

    limit = int(args.get("limit", 12))

    if platform == "instagram":
        from scraper.tiers.social import crawl_instagram
        result = await crawl_instagram(username, post_limit=limit)
    elif platform == "facebook":
        from scraper.tiers.social import crawl_facebook
        result = await crawl_facebook(username, post_limit=limit)
    elif platform == "twitter":
        from scraper.tiers.social import crawl_twitter
        result = await crawl_twitter(username, tweet_limit=limit)
    else:
        raise ValueError(f"unsupported platform: {platform}")

    return {
        "platform": result.platform,
        "success": result.success,
        "error": result.error,
        "profile": result.profile.model_dump() if result.profile else None,
        "post_count": len(result.posts),
        "posts": [p.model_dump() for p in result.posts],
    }


async def _scraper_store(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    from scraper.api import crawl_batch
    from scraper.pipeline.chunk import chunk_content
    from scraper.pipeline.embed import get_embeddings
    from scraper.pipeline.store import ScraperDocumentStore

    urls = args.get("urls", [])
    if not urls:
        raise ValueError("urls is required (non-empty array)")

    tier = args.get("tier", "auto")
    store: ScraperDocumentStore = app.scraped_store

    extracted = await crawl_batch(urls, tier=tier)
    all_ids: list[str] = []

    for content in extracted:
        if not content.markdown:
            continue
        chunks = chunk_content(content)
        if not chunks:
            continue
        texts = [c.text for c in chunks]
        embeddings = get_embeddings(texts)
        ids = await store.store(chunks, embeddings, tier=tier)
        all_ids.extend(ids)

    return {
        "chunks_stored": len(all_ids),
        "urls_crawled": len(urls),
    }


async def _scraper_query(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    from scraper.pipeline.embed import get_embedding
    from scraper.pipeline.store import ScraperDocumentStore

    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")

    n_results = int(args.get("n_results", 5))
    store: ScraperDocumentStore = app.scraped_store

    embedding = get_embedding(query)
    results = await store.query(embedding, n=n_results)
    return {
        "count": len(results),
        "results": results,
    }


async def _scraper_delete(app: Any, _actor: ActorContext, args: dict[str, Any]) -> dict[str, Any]:
    from scraper.pipeline.store import ScraperDocumentStore

    url = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("url is required")

    store: ScraperDocumentStore = app.scraped_store
    deleted = await store.delete_by_url(url)
    return {
        "deleted_count": deleted,
        "url": url,
    }


TOOLS: list[ToolDef] = [
    ToolDef(
        name="xnch_scraper_crawl",
        description=(
            "Crawl a single URL and return clean markdown content with metadata. "
            "Auto-detects the best fetch strategy: static HTTP for simple pages, "
            "headless browser for JS-rendered SPAs. Returns title, markdown, word count, and metadata."
        ),
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to crawl (https://...)",
                },
                "tier": {
                    "type": "string",
                    "enum": ["auto", "static", "browser"],
                    "default": "auto",
                    "description": "Fetch strategy. 'auto' detects based on URL and response.",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=_scraper_crawl,
        allowed_actors=_SCRAPER_ACTORS,
    ),
    ToolDef(
        name="xnch_scraper_batch",
        description=(
            "Crawl multiple URLs concurrently. Auto-detects tier per URL. "
            "Returns title, markdown, and word count for each result."
        ),
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 20,
                    "description": "List of URLs to crawl (max 20).",
                },
                "tier": {
                    "type": "string",
                    "enum": ["auto", "static", "browser"],
                    "default": "auto",
                },
            },
            "required": ["urls"],
            "additionalProperties": False,
        },
        handler=_scraper_batch,
        allowed_actors=_SCRAPER_ACTORS,
    ),
    ToolDef(
        name="xnch_scraper_social",
        description=(
            "Crawl a social media profile and recent posts. "
            "Instagram and Twitter require session credentials (INSTAGRAM_SESSION, TWITTER_* env vars). "
            "Facebook works without auth for public pages. Returns profile info and posts."
        ),
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "facebook", "twitter"],
                    "description": "Social media platform.",
                },
                "username": {
                    "type": "string",
                    "description": "Profile username or page slug.",
                },
                "limit": {
                    "type": "integer",
                    "default": 12,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Max posts to return.",
                },
            },
            "required": ["platform", "username"],
            "additionalProperties": False,
        },
        handler=_scraper_social,
        allowed_actors=_SCRAPER_ACTORS,
    ),
    ToolDef(
        name="xnch_scraper_store",
        description=(
            "Crawl URLs, extract content, chunk, embed, and store in pgvector. "
            "Full pipeline: fetch → extract → chunk → embed → store. Returns chunk count."
        ),
        tier=ToolTier.T1_WRITE,
        input_schema={
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 20,
                    "description": "URLs to crawl and store.",
                },
                "tier": {
                    "type": "string",
                    "enum": ["auto", "static", "browser"],
                    "default": "auto",
                    "description": "Fetch strategy tier.",
                },
            },
            "required": ["urls"],
            "additionalProperties": False,
        },
        handler=_scraper_store,
        allowed_actors=_SCRAPER_ACTORS,
    ),
    ToolDef(
        name="xnch_scraper_query",
        description=(
            "Semantic search against previously stored crawl data. "
            "Uses pgvector cosine similarity with MiniLM-L6-v2 embeddings."
        ),
        tier=ToolTier.T0_READ,
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query to search for.",
                },
                "n_results": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                    "description": "Number of results to return.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_scraper_query,
        allowed_actors=_SCRAPER_ACTORS,
    ),
    ToolDef(
        name="xnch_scraper_delete",
        description="Delete all stored chunks for a URL from the vector database.",
        tier=ToolTier.T1_WRITE,
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Original URL whose data to delete.",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=_scraper_delete,
        allowed_actors=_SCRAPER_ACTORS,
    ),
]
