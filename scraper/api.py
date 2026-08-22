"""Public API for the scraper module."""

import asyncio
import logging
import re
from urllib.parse import urlparse

from .models import CrawlTier, ExtractedContent, SocialResult
from .tiers.browser import crawl_browser, crawl_browser_batch
from .tiers.social import crawl_facebook, crawl_instagram, crawl_twitter
from .tiers.static import crawl_static, crawl_static_batch

logger = logging.getLogger(__name__)

_MIN_CONTENT_LENGTH = 100

_SOCIAL_PATTERNS: list[tuple[str, str, CrawlTier]] = [
    (r"instagram\.com", "instagram", CrawlTier.SOCIAL),
    (r"facebook\.com", "facebook", CrawlTier.SOCIAL),
    (r"(twitter\.com|x\.com)", "twitter", CrawlTier.SOCIAL),
]


def _detect_tier(url: str) -> CrawlTier:
    """Detect which tier to use based on URL patterns."""
    for pattern, _name, tier in _SOCIAL_PATTERNS:
        if re.search(pattern, url):
            return tier
    return CrawlTier.STATIC


def _detect_social_platform(url: str) -> str | None:
    """Return the social platform name if the URL matches one, else None."""
    for pattern, name, _tier in _SOCIAL_PATTERNS:
        if re.search(pattern, url):
            return name
    return None


def _extract_username_from_url(url: str) -> str:
    """Pull the username from a social media profile URL."""
    path = urlparse(url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else ""


def _social_to_extracted(result: SocialResult) -> ExtractedContent:
    """Convert a SocialResult into an ExtractedContent."""
    sections: list[str] = []

    if result.profile:
        p = result.profile
        if p.display_name:
            sections.append(f"# {p.display_name} ({p.username})")
        else:
            sections.append(f"# @{p.username}")
        if p.bio:
            sections.append(p.bio)
        stats = []
        if p.follower_count is not None:
            stats.append(f"**Followers:** {p.follower_count:,}")
        if p.following_count is not None:
            stats.append(f"**Following:** {p.following_count:,}")
        if p.post_count is not None:
            stats.append(f"**Posts:** {p.post_count:,}")
        if stats:
            sections.append(" | ".join(stats))

    for i, post in enumerate(result.posts):
        sections.append(f"\n## Post {i + 1}")
        if post.text:
            sections.append(post.text)
        meta_parts = []
        if post.likes is not None:
            meta_parts.append(f"{post.likes} likes")
        if post.comments is not None:
            meta_parts.append(f"{post.comments} comments")
        if post.shares is not None:
            meta_parts.append(f"{post.shares} shares")
        if post.timestamp:
            meta_parts.append(post.timestamp.strftime("%Y-%m-%d %H:%M"))
        if meta_parts:
            sections.append(f"*{' · '.join(meta_parts)}*")
        if post.post_url:
            sections.append(f"[Link]({post.post_url})")

    markdown = "\n\n".join(sections)
    profile_url = result.profile.profile_url if result.profile else ""
    title = (
        (result.profile.display_name or result.profile.username)
        if result.profile
        else result.platform
    )

    metadata: dict[str, str] = {"platform": result.platform}
    if result.error:
        metadata["error"] = result.error

    return ExtractedContent(
        url=profile_url,
        title=title,
        markdown=markdown,
        metadata=metadata,
    )


def _resolve_tier(tier: CrawlTier | str) -> CrawlTier:
    """Coerce a tier string or CrawlTier enum into CrawlTier."""
    if isinstance(tier, CrawlTier):
        return tier
    return CrawlTier(tier.lower())


async def crawl(
    url: str,
    tier: CrawlTier | str = "auto",
    headless: bool = True,
) -> ExtractedContent:
    """Crawl a single URL and return extracted content.

    When tier is ``"auto"`` the function detects the appropriate strategy:
    social-platform URLs use the social tier, while other URLs try static
    first and fall back to browser if the extracted content is too short.
    """
    resolved = _resolve_tier(tier) if tier != "auto" else None

    # --- Auto-detect social ---
    if resolved is None or resolved == CrawlTier.SOCIAL:
        platform = _detect_social_platform(url)
        if platform:
            return await _crawl_social(url, platform)

    # --- Auto or explicit static / browser ---
    if resolved is not None and resolved == CrawlTier.BROWSER:
        return await crawl_browser(url, headless=headless)

    # Try static first
    result = await crawl_static(url)
    if len(result.markdown) >= _MIN_CONTENT_LENGTH:
        return result

    # Content too short — fall back to browser if auto or explicitly static
    if resolved is None or resolved == CrawlTier.STATIC:
        logger.info(
            "Static content short (%d chars) for %s, falling back to browser",
            len(result.markdown),
            url,
        )
        return await crawl_browser(url, headless=headless)

    return result


async def _crawl_social(url: str, platform: str) -> ExtractedContent:
    """Dispatch a social-media URL to the right crawler and convert."""
    username = _extract_username_from_url(url)
    if not username:
        return ExtractedContent(url=url, markdown="", metadata={"error": f"Could not extract username from {url}"})

    if platform == "instagram":
        result = await crawl_instagram(username)
    elif platform == "facebook":
        result = await crawl_facebook(url)
    elif platform == "twitter":
        result = await crawl_twitter(username)
    else:
        return ExtractedContent(url=url, markdown="", metadata={"error": f"Unknown social platform: {platform}"})

    return _social_to_extracted(result)


async def crawl_batch(
    urls: list[str],
    tier: CrawlTier | str = "auto",
    max_concurrent: int = 5,
) -> list[ExtractedContent]:
    """Crawl multiple URLs concurrently, returning results in input order.

    When tier is ``"auto"``, URLs are grouped by detected tier so batch
    methods can be used where available (static and browser).
    """
    if not urls:
        return []

    resolved = _resolve_tier(tier) if tier != "auto" else None

    # Explicit tier — dispatch everything the same way
    if resolved is not None:
        return await _batch_by_tier(urls, resolved, headless=True, max_concurrent=max_concurrent)

    # Auto mode — group by detected tier
    social_groups: dict[str, list[tuple[int, str, str]]] = {}
    static_urls: list[tuple[int, str]] = []

    for idx, url in enumerate(urls):
        platform = _detect_social_platform(url)
        if platform:
            social_groups.setdefault(platform, []).append((idx, url, platform))
        else:
            static_urls.append((idx, url))

    results: list[ExtractedContent | None] = [None] * len(urls)

    # Static batch (falls back to browser individually if content is short)
    if static_urls:
        batch = [u for _, u in static_urls]
        extracted = await crawl_static_batch(batch, max_concurrent=max_concurrent)

        # Check each result and fall back to browser if needed
        fallback_urls: list[tuple[int, str]] = []
        for (idx, _url), content in zip(static_urls, extracted):
            if len(content.markdown) < _MIN_CONTENT_LENGTH:
                fallback_urls.append((idx, _url))
            else:
                results[idx] = content

        if fallback_urls:
            for idx, url in fallback_urls:
                results[idx] = await crawl_browser(url)

    # Social — dispatch individually (no shared batch endpoint)
    for platform, group in social_groups.items():
        tasks = [_crawl_social(url, platform) for _idx, url, _platform in group]
        social_results = await asyncio.gather(*tasks)
        for (idx, _url, _pl), res in zip(group, social_results):
            results[idx] = res

    return [r if r is not None else ExtractedContent(url=u, markdown="") for r, u in zip(results, urls)]


async def _batch_by_tier(
    urls: list[str],
    tier: CrawlTier,
    *,
    headless: bool = True,
    max_concurrent: int = 5,
) -> list[ExtractedContent]:
    """Dispatch a batch of URLs all using the same explicit tier."""
    if tier == CrawlTier.STATIC:
        return await crawl_static_batch(urls, max_concurrent=max_concurrent)
    if tier == CrawlTier.BROWSER:
        return await crawl_browser_batch(urls, headless=headless, max_concurrent=max_concurrent)
    # Social — no shared batch method, run individually with concurrency limit
    sem = asyncio.Semaphore(max_concurrent)

    async def _limited(url: str) -> ExtractedContent:
        async with sem:
            platform = _detect_social_platform(url)
            if platform:
                return await _crawl_social(url, platform)
            return await crawl_static(url)

    return list(await asyncio.gather(*[_limited(u) for u in urls]))
