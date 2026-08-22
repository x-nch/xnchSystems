"""Configuration for the scraper module.

Scraper-specific settings are now in ``xnch.config.ScraperSettings``
(accessible via ``settings.scraper``). This module is retained for
backwards compatibility but delegates to the central config.
"""

from pydantic import BaseModel, Field


class ScraperConfig(BaseModel):
    """Settings controlling crawler behaviour and resource limits."""

    max_concurrent_requests: int = Field(default=10, ge=1)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default="Mozilla/5.0 (compatible; xnchBot/1.0)")
    respect_robots_txt: bool = True
    retry_count: int = Field(default=2, ge=0)


class PipelineConfig(BaseModel):
    """Settings for the extract → chunk → embed → store pipeline."""

    chunk_size_tokens: int = Field(default=512, ge=64)
    chunk_overlap_tokens: int = Field(default=64, ge=0)
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    embedding_batch_size: int = Field(default=64, ge=1)
