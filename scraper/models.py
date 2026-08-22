"""Data models for the scraper module."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CrawlTier(StrEnum):
    """Fetch strategy tiers."""

    STATIC = "static"
    BROWSER = "browser"
    SOCIAL = "social"


class CrawlRequest(BaseModel):
    """Input for a single crawl operation."""

    url: str
    tier: CrawlTier = CrawlTier.STATIC
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)


class RawPage(BaseModel):
    """Raw fetched page before extraction."""

    url: str
    html: str
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractedContent(BaseModel):
    """Cleaned content after extraction."""

    url: str
    title: str | None = None
    markdown: str
    language: str | None = None
    published_date: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ContentChunk(BaseModel):
    """A chunk of extracted content ready for embedding."""

    chunk_id: str
    source_url: str
    text: str
    index: int
    total_chunks: int
    metadata: dict[str, str] = Field(default_factory=dict)


class StoredDocument(BaseModel):
    """A document that has been stored in the vector database."""

    doc_id: str
    chunk_ids: list[str]
    source_url: str
    stored_at: datetime = Field(default_factory=datetime.utcnow)


class SocialProfile(BaseModel):
    """Profile information for a social media account."""

    platform: str
    username: str
    display_name: str | None = None
    bio: str | None = None
    follower_count: int | None = None
    following_count: int | None = None
    post_count: int | None = None
    profile_url: str
    profile_image_url: str | None = None
    verified: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class SocialPost(BaseModel):
    """A single social media post."""

    post_id: str
    platform: str
    author: str
    text: str
    timestamp: datetime | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    media_urls: list[str] = Field(default_factory=list)
    post_url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class SocialResult(BaseModel):
    """Aggregated result from a social media crawl."""

    platform: str
    profile: SocialProfile | None = None
    posts: list[SocialPost] = Field(default_factory=list)
    success: bool = True
    error: str | None = None
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
