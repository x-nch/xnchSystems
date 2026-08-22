"""Browser-based crawling using Playwright and Crawlee."""

import logging
from datetime import timedelta

import trafilatura
from bs4 import BeautifulSoup
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.fingerprint_suite import DefaultFingerprintGenerator, HeaderGeneratorOptions

from ..models import ExtractedContent

logger = logging.getLogger(__name__)


def _make_fingerprint_generator() -> DefaultFingerprintGenerator:
    """Create a fingerprint generator targeting Chrome on desktop."""
    return DefaultFingerprintGenerator(
        header_options=HeaderGeneratorOptions(browsers=["chrome"]),
    )


async def crawl_browser(
    url: str,
    wait_for: str | None = None,
    headless: bool = True,
    timeout: float = 30.0,
) -> ExtractedContent:
    """Crawl a single URL with a real browser for JS-rendered content.

    Uses Playwright via Crawlee with fingerprint generation for anti-detection.
    Extracts main content via trafilatura, falling back to inner_text on failure.
    """
    results: list[ExtractedContent] = []
    crawler = PlaywrightCrawler(
        headless=headless,
        fingerprint_generator=_make_fingerprint_generator(),
        navigation_timeout=timedelta(seconds=timeout),
    )

    @crawler.router.default_handler
    async def handler(context: PlaywrightCrawlingContext) -> None:
        page = context.page

        if wait_for:
            try:
                await page.wait_for_selector(wait_for, timeout=int(timeout * 1000))
            except Exception as exc:
                logger.warning("wait_for selector '%s' not found on %s: %s", wait_for, url, exc)

        try:
            html = await page.content()
        except Exception as exc:
            logger.warning("Failed to get HTML from %s: %s", url, exc)
            html = ""

        soup = BeautifulSoup(html, "html.parser")
        page_title = soup.title.string.strip() if soup.title and soup.title.string else None

        # Extract via trafilatura
        markdown = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            favor_precision=False,
        )

        # Fallback: inner_text if trafilatura returns nothing useful
        if not markdown or len(markdown) < 100:
            logger.info("Trafilatura returned short content for %s, falling back to inner_text", url)
            try:
                markdown = await page.inner_text("body")
            except Exception:
                markdown = ""

        metadata: dict[str, str] = {}
        resp = context.response
        if resp:
            for key in ("content-type", "last-modified", "etag"):
                val = resp.headers.get(key)
                if val:
                    metadata[key] = val

        results.append(ExtractedContent(
            url=url,
            title=page_title,
            markdown=markdown.strip(),
            metadata=metadata,
        ))

    try:
        await crawler.run([url])
    except Exception as exc:
        logger.warning("Crawler failed for %s: %s", url, exc)

    if results:
        return results[0]

    return ExtractedContent(url=url, markdown="", metadata={"error": "crawl returned no results"})


async def crawl_browser_batch(
    urls: list[str],
    headless: bool = True,
    max_concurrent: int = 3,
) -> list[ExtractedContent]:
    """Crawl multiple URLs with a shared browser context.

    Results are returned in the same order as the input URLs.
    """
    from crawlee.storages import RequestQueue

    url_index = {u: i for i, u in enumerate(urls)}
    results: list[ExtractedContent | None] = [None] * len(urls)

    crawler = PlaywrightCrawler(
        headless=headless,
        fingerprint_generator=_make_fingerprint_generator(),
        max_requests_per_crawl=len(urls),
    )

    @crawler.router.default_handler
    async def handler(context: PlaywrightCrawlingContext) -> None:
        current_url = context.request.url
        page = context.page

        try:
            html = await page.content()
        except Exception as exc:
            logger.warning("Failed to get HTML from %s: %s", current_url, exc)
            html = ""

        soup = BeautifulSoup(html, "html.parser")
        page_title = soup.title.string.strip() if soup.title and soup.title.string else None

        markdown = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            favor_precision=False,
        )

        if not markdown or len(markdown) < 100:
            try:
                markdown = await page.inner_text("body")
            except Exception:
                markdown = ""

        metadata: dict[str, str] = {}
        resp = context.response
        if resp:
            for key in ("content-type", "last-modified", "etag"):
                val = resp.headers.get(key)
                if val:
                    metadata[key] = val

        idx = url_index.get(current_url)
        if idx is not None:
            results[idx] = ExtractedContent(
                url=current_url,
                title=page_title,
                markdown=markdown.strip(),
                metadata=metadata,
            )

    try:
        await crawler.run(urls)
    except Exception as exc:
        logger.warning("Batch crawl failed: %s", exc)

    return [
        r if r is not None else ExtractedContent(url=u, markdown="", metadata={"error": "crawl returned no results"})
        for u, r in zip(urls, results)
    ]
