"""Tiered crawling strategies from lightweight HTTP to full browser."""


def __getattr__(name: str):  # noqa: ANN001
    if name == "crawl_browser":
        from .browser import crawl_browser
        return crawl_browser
    if name == "crawl_browser_batch":
        from .browser import crawl_browser_batch
        return crawl_browser_batch
    if name == "crawl_instagram":
        from .social import crawl_instagram
        return crawl_instagram
    if name == "crawl_twitter":
        from .social import crawl_twitter
        return crawl_twitter
    if name == "crawl_facebook":
        from .social import crawl_facebook
        return crawl_facebook
    if name == "crawl_static":
        from .static import crawl_static
        return crawl_static
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "crawl_static",
    "crawl_browser",
    "crawl_browser_batch",
    "crawl_instagram",
    "crawl_twitter",
    "crawl_facebook",
]
