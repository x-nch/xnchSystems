"""Content extraction — HTML to clean markdown."""

import logging

import httpx
import markdownify
import trafilatura
from trafilatura.settings import use_config as trafilatura_config

from ..models import ExtractedContent

logger = logging.getLogger(__name__)


def extract_content(html: str, url: str = "") -> ExtractedContent:
    """Extract main content from HTML as clean markdown.

    Uses trafilatura as primary extractor. Falls back to markdownify
    if trafilatura returns empty or very short content.
    """
    metadata: dict[str, str] = {}

    # --- primary: trafilatura ---
    trafilatura_cfg = trafilatura_config()
    result = trafilatura.extract(
        html,
        output_format="json",
        include_comments=False,
        include_tables=True,
        url=url,
        config=trafilatura_cfg,
    )

    markdown_text = ""
    title: str | None = None
    language: str | None = None

    if result:
        import json

        data = json.loads(result)
        markdown_text = data.get("text", "")
        title = data.get("title") or None
        language = data.get("language") or None
        if data.get("author"):
            metadata["author"] = data["author"]
        if data.get("date"):
            metadata["published_date"] = data["date"]
        if data.get("sitename"):
            metadata["sitename"] = data["sitename"]

    # --- fallback: markdownify ---
    if len(markdown_text.strip()) < 20:
        logger.info("trafilatura returned minimal content, falling back to markdownify")
        markdown_text = markdownify.markdownify(
            html,
            heading_style="ATX",
            strip=["script", "style", "nav", "footer"],
        )
        # collapse excess whitespace
        lines = [line.strip() for line in markdown_text.splitlines()]
        markdown_text = "\n".join(line for line in lines if line)

    # --- title fallback: meta tags ---
    if not title:
        title = _extract_title_from_html(html)

    return ExtractedContent(
        url=url,
        title=title,
        markdown=markdown_text.strip(),
        language=language,
        metadata=metadata,
    )


def _extract_title_from_html(html: str) -> str | None:
    """Pull <title> tag from raw HTML as last-resort fallback."""
    import re

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip() or None
    return None


async def extract_from_url(url: str) -> ExtractedContent:
    """Fetch a URL and extract its content."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; xnchBot/1.0)"},
        )
        resp.raise_for_status()
    return extract_content(resp.text, url=url)
