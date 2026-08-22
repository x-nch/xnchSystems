"""Social media platform crawlers for Instagram, Twitter, and Facebook."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..models import SocialPost, SocialProfile, SocialResult

logger = logging.getLogger(__name__)

_IG_WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


def _load_instagram_session() -> dict[str, str] | None:
    """Load Instagram session from env var or file."""
    session_str = os.environ.get("INSTAGRAM_SESSION")
    if session_str:
        try:
            return json.loads(session_str)
        except json.JSONDecodeError:
            return {"sessionid": session_str}

    session_path = Path.home() / ".instagram_session"
    if session_path.exists():
        try:
            return json.loads(session_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


async def crawl_instagram(username: str, post_limit: int = 12) -> SocialResult:
    """Crawl Instagram profile and posts via aiograpi or public web fallback.

    Tries aiograpi with session cookies first. Falls back to public web
    endpoint for basic profile data when no session is available.
    """
    try:
        return await _crawl_instagram_aiograpi(username, post_limit)
    except Exception as aiograpi_err:
        logger.warning("aiograpi failed for @%s: %s — trying web fallback", username, aiograpi_err)
        try:
            return await _crawl_instagram_web(username, post_limit)
        except Exception as web_err:
            logger.error("All Instagram methods failed for @%s: %s", username, web_err)
            return SocialResult(platform="instagram", success=False, error=f"aiograpi: {aiograpi_err}; web: {web_err}")


async def _crawl_instagram_aiograpi(username: str, post_limit: int) -> SocialResult:
    """Instagram crawl via aiograpi private API."""
    from aiograpi import Client

    cl = Client()
    session = _load_instagram_session()
    if session:
        await cl.login(**session)
    else:
        raise RuntimeError("No Instagram session available — set INSTAGRAM_SESSION env var or ~/.instagram_session file")

    user = await cl.user_info_by_username(username)
    profile = SocialProfile(
        platform="instagram",
        username=user.username,
        display_name=user.full_name,
        bio=user.biography,
        follower_count=user.follower_count,
        following_count=user.following_count,
        post_count=user.media_count,
        profile_url=f"https://instagram.com/{user.username}",
        profile_image_url=user.profile_pic_url_hd or user.profile_pic_url,
        verified=user.is_verified,
    )

    posts = []
    async for media in cl.user_medias(user.pk, amount=post_limit):
        posts.append(SocialPost(
            post_id=str(media.pk),
            platform="instagram",
            author=user.username,
            text=media.caption_text or "",
            timestamp=media.taken_at,
            likes=media.like_count,
            comments=media.comment_count,
            shares=None,
            media_urls=[m.url for m in (media.resources or []) if m.url] or ([media.thumbnail_url] if media.thumbnail_url else []),
            post_url=f"https://instagram.com/p/{media.code}/" if media.code else None,
            metadata={"media_type": str(media.media_type)},
        ))

    return SocialResult(platform="instagram", profile=profile, posts=posts)


async def _crawl_instagram_web(username: str, post_limit: int) -> SocialResult:
    """Instagram crawl via public web endpoint (limited data, no login)."""
    async with httpx.AsyncClient(headers=_IG_WEB_HEADERS, timeout=15.0) as client:
        resp = await client.get(f"https://www.instagram.com/{username}/")
        resp.raise_for_status()

    # Try to extract from embedded JSON data
    text = resp.text
    profile = SocialProfile(
        platform="instagram",
        username=username,
        profile_url=f"https://instagram.com/{username}",
    )

    # Parse meta tags for basic info
    import re
    title_match = re.search(r'<title>([^<]+)</title>', text)
    if title_match:
        profile.display_name = title_match.group(1).split("(")[0].strip()

    desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', text)
    if desc_match:
        desc = desc_match.group(1)
        follower_match = re.search(r"([\d.]+[KMB]?)\s+Followers", desc)
        if follower_match:
            profile.follower_count = _parse_count(follower_match.group(1))
        following_match = re.search(r"([\d.]+[KMB]?)\s+Following", desc)
        if following_match:
            profile.following_count = _parse_count(following_match.group(1))
        posts_match = re.search(r"([\d,]+)\s+Posts", desc)
        if posts_match:
            profile.post_count = int(posts_match.group(1).replace(",", ""))
        profile.bio = desc.split('" followers,')[0].split(" Followers, ")[-1] if " Followers, " in desc else None

    return SocialResult(platform="instagram", profile=profile, posts=[], error="Web fallback: limited data, no posts")


def _parse_count(s: str) -> int:
    """Parse Instagram-style counts like '1.5M', '234K', '12345'."""
    s = s.replace(",", "")
    if s.endswith("M"):
        return int(float(s[:-1]) * 1_000_000)
    if s.endswith("K"):
        return int(float(s[:-1]) * 1_000)
    if s.endswith("B"):
        return int(float(s[:-1]) * 1_000_000_000)
    return int(float(s))


async def crawl_facebook(page_url: str, post_limit: int = 20) -> SocialResult:
    """Crawl Facebook public page posts via GraphQL scraper (no login)."""
    try:
        from fb_scraper_request import FacebookGraphqlScraper

        # Extract page username from URL
        page_username = page_url.rstrip("/").split("/")[-1]
        if "?" in page_username:
            page_username = page_username.split("?")[0]

        fb = FacebookGraphqlScraper()
        result = fb.get_user_posts(page_username, days_limit=7)

        profile = SocialProfile(
            platform="facebook",
            username=page_username,
            profile_url=f"https://facebook.com/{page_username}",
        )

        posts = []
        for item in (result.get("data", []) or [])[:post_limit]:
            posts.append(SocialPost(
                post_id=item.get("post_id", ""),
                platform="facebook",
                author=page_username,
                text=item.get("text", ""),
                timestamp=_parse_fb_timestamp(item.get("timestamp")),
                likes=_safe_int(item.get("reaction_count")),
                comments=_safe_int(item.get("comment_count")),
                shares=_safe_int(item.get("share_count")),
                media_urls=item.get("media", []) if isinstance(item.get("media"), list) else [],
                post_url=item.get("post_url"),
            ))

        return SocialResult(platform="facebook", profile=profile, posts=posts)

    except Exception as e:
        logger.error("Facebook crawl failed for %s: %s", page_url, e)
        return SocialResult(platform="facebook", success=False, error=str(e))


async def crawl_twitter(username: str, tweet_limit: int = 20) -> SocialResult:
    """Crawl Twitter/X profile and tweets via twikit."""
    try:
        from twikit import Client as TwikitClient

        client = TwikitClient()
        username_creds = os.environ.get("TWITTER_USERNAME")
        password = os.environ.get("TWITTER_PASSWORD")
        email = os.environ.get("TWITTER_EMAIL")

        if not all([username_creds, password, email]):
            return SocialResult(
                platform="twitter",
                success=False,
                error="Missing credentials — set TWITTER_USERNAME, TWITTER_PASSWORD, TWITTER_EMAIL env vars",
            )

        await client.login(
            auth_info_1=username_creds,
            auth_info_2=email,
            password=password,
        )

        user = await client.get_user_by_screen_name(username)
        profile = SocialProfile(
            platform="twitter",
            username=user.screen_name,
            display_name=user.name,
            bio=user.description,
            follower_count=user.followers_count,
            following_count=user.following_count,
            post_count=user.statuses_count,
            profile_url=f"https://x.com/{user.screen_name}",
            profile_image_url=user.profile_image_url,
            verified=user.verified if hasattr(user, "verified") else False,
        )

        tweets = await client.get_user_tweets(user.id, tweet_type="Tweets", count=tweet_limit)
        posts = []
        for tweet in tweets:
            posts.append(SocialPost(
                post_id=tweet.id,
                platform="twitter",
                author=user.screen_name,
                text=tweet.full_text or "",
                timestamp=tweet.created_at_datetime if hasattr(tweet, "created_at_datetime") else None,
                likes=tweet.favorite_count,
                comments=tweet.reply_count,
                shares=tweet.retweet_count,
                media_urls=[m.get("url", "") for m in (tweet.media or []) if m.get("url")],
                post_url=f"https://x.com/{user.screen_name}/status/{tweet.id}",
            ))

        return SocialResult(platform="twitter", profile=profile, posts=posts)

    except Exception as e:
        logger.error("Twitter crawl failed for @%s: %s", username, e)
        return SocialResult(platform="twitter", success=False, error=str(e))


def _parse_fb_timestamp(ts: str | None) -> datetime | None:
    """Parse Facebook timestamp string to datetime."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _safe_int(val: str | int | None) -> int | None:
    """Safely convert a value to int."""
    if val is None:
        return None
    try:
        return int(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None
