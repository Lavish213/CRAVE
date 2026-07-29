from __future__ import annotations

"""
oEmbed-based metadata extraction for shared social links.

Why this exists: share_parser_worker.py previously did a plain HTTP GET and
read `og:title` / `<title>` off the raw HTML. That works for traditional
server-rendered pages (blogs, restaurant sites) but almost never works for
TikTok or Instagram — both are JS-rendered single-page apps, and an
unauthenticated GET typically returns a generic login-wall shell with no real
title, not the video's caption.

oEmbed is the fix: it's an open, purpose-built format these platforms publish
specifically so third parties can pull a post's title/author/thumbnail
without scraping. TikTok and YouTube's oEmbed endpoints are free and need no
auth. Instagram's oEmbed requires a registered-and-reviewed Meta developer
app (graph.facebook.com/.../instagram_oembed with an access token) — that's
a real account-setup step, not a code change, so it's stubbed here rather
than implemented. get_oembed_title() falls through cleanly to the existing
HTML-scrape path for "instagram" and any source type without a handler.
"""

import logging
from typing import Optional

from app.services.network.http_fetcher import fetch

logger = logging.getLogger(__name__)

TIKTOK_OEMBED_URL = "https://www.tiktok.com/oembed"
YOUTUBE_OEMBED_URL = "https://www.youtube.com/oembed"

# Populate once an Instagram Meta developer app is registered and reviewed
# for oEmbed Read access. Until then, "instagram" falls through to the
# existing HTML-scrape fallback in share_parser_worker.py — weaker, but not
# a hard failure.
INSTAGRAM_OEMBED_URL = "https://graph.facebook.com/v19.0/instagram_oembed"


def _fetch_oembed(endpoint: str, url: str, *, extra_params: Optional[dict] = None) -> Optional[dict]:
    try:
        params = {"url": url, "format": "json"}
        if extra_params:
            params.update(extra_params)

        response = fetch(endpoint, method="GET", params=params, timeout=10.0)

        if response.status_code != 200:
            logger.debug(
                "oembed_http_error endpoint=%s url=%s status=%s",
                endpoint, url, response.status_code,
            )
            return None

        return response.json()

    except Exception as exc:
        logger.debug("oembed_fetch_failed endpoint=%s url=%s error=%s", endpoint, url, exc)
        return None


def get_tiktok_oembed(url: str) -> Optional[dict]:
    """Returns {'title': <caption>, 'author_name': ..., 'thumbnail_url': ...} or None."""
    return _fetch_oembed(TIKTOK_OEMBED_URL, url)


def get_youtube_oembed(url: str) -> Optional[dict]:
    """Returns {'title': <video title>, 'author_name': ..., 'thumbnail_url': ...} or None."""
    return _fetch_oembed(YOUTUBE_OEMBED_URL, url)


def get_instagram_oembed(url: str) -> Optional[dict]:
    """
    Stub — requires INSTAGRAM_OEMBED_ACCESS_TOKEN (a reviewed Meta app
    token) once that's set up. Returns None until then, which is a safe
    no-op: callers fall back to HTML scraping.
    """
    import os
    token = os.getenv("INSTAGRAM_OEMBED_ACCESS_TOKEN")
    if not token:
        return None
    return _fetch_oembed(INSTAGRAM_OEMBED_URL, url, extra_params={"access_token": token})


_OEMBED_HANDLERS = {
    "tiktok": get_tiktok_oembed,
    "youtube": get_youtube_oembed,
    "instagram": get_instagram_oembed,
}


def get_oembed_text(source_type: str, url: str) -> Optional[str]:
    """
    Returns the best available text (caption or title) for a shared URL via
    the platform's oEmbed endpoint, or None if unsupported/unavailable —
    callers should fall back to HTML scraping on None, not treat it as an
    error.
    """
    data = get_oembed_data(source_type, url)
    if not data:
        return None

    title = data.get("title")
    if title and isinstance(title, str) and title.strip():
        return title.strip()

    return None


def get_oembed_data(source_type: str, url: str) -> Optional[dict]:
    """
    Returns the normalized oEmbed payload for a shared URL — title,
    thumbnail_url, html, author_name — or None if unsupported/unavailable.

    Previously only the title was ever pulled out of this response
    (get_oembed_text) and the rest was discarded, so there was no way to
    show a preview image or attribution for a matched share. This is the
    same underlying fetch, just returning the full dict so callers
    (share_parser_worker.py) can persist thumbnail_url/embed_html/author_name
    onto the CraveItem instead of just the caption text.
    """
    handler = _OEMBED_HANDLERS.get((source_type or "").strip().lower())
    if not handler:
        return None

    data = handler(url)
    if not data:
        return None

    title = data.get("title")
    title = title.strip() if isinstance(title, str) and title.strip() else None

    thumbnail_url = data.get("thumbnail_url")
    thumbnail_url = thumbnail_url.strip() if isinstance(thumbnail_url, str) and thumbnail_url.strip() else None

    html = data.get("html")
    html = html.strip() if isinstance(html, str) and html.strip() else None

    author_name = data.get("author_name")
    author_name = author_name.strip() if isinstance(author_name, str) and author_name.strip() else None

    if not any((title, thumbnail_url, html, author_name)):
        return None

    return {
        "title": title,
        "thumbnail_url": thumbnail_url,
        "html": html,
        "author_name": author_name,
    }
