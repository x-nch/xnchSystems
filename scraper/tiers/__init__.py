"""Tiered crawling strategies from lightweight HTTP to full browser."""

from .browser import crawl_browser, crawl_browser_batch
from .social import crawl_facebook, crawl_instagram, crawl_twitter
from .static import crawl_static

__all__ = [
    "crawl_static",
    "crawl_browser",
    "crawl_browser_batch",
    "crawl_instagram",
    "crawl_twitter",
    "crawl_facebook",
]
