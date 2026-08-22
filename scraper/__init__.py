"""Web crawling stack with tiered fetch strategies and processing pipeline."""


def crawl(*args, **kwargs):  # type: ignore[no-untyped-def]
    from .api import crawl as _crawl
    return _crawl(*args, **kwargs)


def crawl_batch(*args, **kwargs):  # type: ignore[no-untyped-def]
    from .api import crawl_batch as _crawl_batch
    return _crawl_batch(*args, **kwargs)


__all__ = ["crawl", "crawl_batch"]
