"""Static HTTP crawling using httpx, trafilatura, and markdownify."""

import asyncio
import logging
from typing import Any

import httpx
import markdownify
import trafilatura
from bs4 import BeautifulSoup

from ..models import ExtractedContent

logger = logging.getLogger(__name__)

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _extract_with_bs4(html: str) -> tuple[str | None, str]:
    """Fallback: pull <title> and convert body to markdown via markdownify."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    body = soup.body or soup
    md = markdownify.markdownify(
        str(body),
        heading_style="ATX",
        strip=["script", "style", "nav", "footer", "header"],
    )
    return title, md.strip()


def _metadata_from_response(resp: httpx.Response) -> dict[str, str]:
    """Collect useful headers as metadata."""
    meta: dict[str, str] = {}
    for key in ("content-type", "last-modified", "etag"):
        val = resp.headers.get(key)
        if val:
            meta[key] = val
    return meta


async def crawl_static(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> ExtractedContent:
    """Fetch a URL via plain HTTP and extract main content.

    Uses trafilatura for article extraction with a markdownify fallback.
    Returns a best-effort result even on errors (error stored in metadata).
    """
    req_headers = {"User-Agent": _DEFAULT_UA}
    if headers:
        req_headers.update(headers)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            resp = await client.get(url, headers=req_headers)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return ExtractedContent(
            url=url,
            markdown="",
            metadata={"error": str(exc)},
        )

    html = resp.text
    meta = _metadata_from_response(resp)

    # --- trafilatura extraction ---
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        output_format="txt",
        favor_precision=False,
    )
    title = trafilatura.extract(
        html,
        output_format="txt",
        only_with_metadata=False,
    )
    # trafilatura doesn't have a clean title extractor; fall back to BS4
    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.string.strip() if soup.title and soup.title.string else None

    # If trafilatura returned substantial content, use it
    if extracted and len(extracted) > 100:
        return ExtractedContent(
            url=url,
            title=page_title,
            markdown=extracted,
            metadata=meta,
        )

    # --- fallback to markdownify ---
    logger.info("Trafilatura returned short content for %s, falling back to markdownify", url)
    bs_title, md = _extract_with_bs4(html)

    return ExtractedContent(
        url=url,
        title=page_title or bs_title,
        markdown=md,
        metadata=meta,
    )


async def crawl_static_batch(
    urls: list[str],
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    max_concurrent: int = 5,
) -> list[ExtractedContent]:
    """Crawl multiple URLs concurrently with rate limiting.

    Results are returned in the same order as the input URLs.
    """
    sem = asyncio.Semaphore(max_concurrent)

    async def _limited(url: str) -> ExtractedContent:
        async with sem:
            return await crawl_static(url, headers=headers, timeout=timeout)

    return list(await asyncio.gather(*[_limited(u) for u in urls]))
