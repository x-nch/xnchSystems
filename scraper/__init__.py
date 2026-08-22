"""Web crawling stack with tiered fetch strategies and processing pipeline."""

from .api import crawl, crawl_batch

__all__ = ["crawl", "crawl_batch"]
