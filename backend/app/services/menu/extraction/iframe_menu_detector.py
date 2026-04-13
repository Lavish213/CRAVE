from __future__ import annotations

import logging
import re
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urldefrag

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


MAX_IFRAMES = 12


# ---------------------------------------------------------
# Provider iframe indicators
# ---------------------------------------------------------

PROVIDER_DOMAINS = [

    "toasttab.com",
    "square.site",
    "squareup.com",
    "clover.com",
    "chownow.com",
    "popmenu.com",
    "spoton.com",
    "order.online",
    "menufy.com",
    "gloriafood.com",
    "bentoboxcdn.com",
    "getbento.com",
    "lunchbox.io",
    "olo.com",
    "upserve.com",
]


# ---------------------------------------------------------
# Known non-menu embeds
# ---------------------------------------------------------

IGNORED_DOMAINS = [

    "youtube.com",
    "google.com/maps",
    "vimeo.com",
    "doubleclick.net",
    "googletagmanager",
    "google-analytics",
    "analytics",
    "facebook.com/plugins",
]


# ---------------------------------------------------------
# Regex fallback for iframe URLs inside scripts
# ---------------------------------------------------------

SCRIPT_IFRAME_REGEX = re.compile(
    r'https?://[^\s"\'<>]+',
    re.IGNORECASE,
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean_url(url: str) -> str:

    url = url.strip()

    if not url:
        return ""

    url, _ = urldefrag(url)

    return url


def _normalize_url(base_url: Optional[str], src: Optional[str]) -> Optional[str]:

    if not src:
        return None

    src = _clean_url(src)

    if not src:
        return None

    try:

        if base_url:
            url = urljoin(base_url, src)
        else:
            url = src

        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return None

        return url

    except Exception:

        return None


def _iframe_score(url: str) -> int:

    url_lower = url.lower()

    score = 0

    for provider in PROVIDER_DOMAINS:
        if provider in url_lower:
            score += 5

    if "menu" in url_lower:
        score += 3

    if "order" in url_lower:
        score += 2

    if "food" in url_lower:
        score += 1

    return score


def _is_valid_iframe(url: str) -> bool:

    url_lower = url.lower()

    for bad in IGNORED_DOMAINS:
        if bad in url_lower:
            return False

    for provider in PROVIDER_DOMAINS:
        if provider in url_lower:
            return True

    if "menu" in url_lower:
        return True

    if "order" in url_lower:
        return True

    if "food" in url_lower:
        return True

    return False


# ---------------------------------------------------------
# Script scanning
# ---------------------------------------------------------

def _extract_iframes_from_scripts(html: str) -> List[str]:

    matches = SCRIPT_IFRAME_REGEX.findall(html)

    urls: List[str] = []

    for url in matches:

        if _is_valid_iframe(url):
            urls.append(url)

    return urls


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def detect_menu_iframes(
    html: str,
    base_url: Optional[str] = None,
) -> List[str]:

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    discovered: Set[str] = set()

    # ---------------------------------------------------------
    # iframe tags
    # ---------------------------------------------------------

    for iframe in soup.find_all("iframe"):

        src = (
            iframe.get("src")
            or iframe.get("data-src")
            or iframe.get("data-lazy-src")
            or iframe.get("data-url")
        )

        url = _normalize_url(base_url, src)

        if not url:
            continue

        if not _is_valid_iframe(url):
            continue

        discovered.add(url)

        if len(discovered) >= MAX_IFRAMES:
            break


    # ---------------------------------------------------------
    # embed tags
    # ---------------------------------------------------------

    for embed in soup.find_all("embed"):

        src = embed.get("src")

        url = _normalize_url(base_url, src)

        if not url:
            continue

        if not _is_valid_iframe(url):
            continue

        discovered.add(url)

        if len(discovered) >= MAX_IFRAMES:
            break


    # ---------------------------------------------------------
    # object tags
    # ---------------------------------------------------------

    for obj in soup.find_all("object"):

        src = obj.get("data")

        url = _normalize_url(base_url, src)

        if not url:
            continue

        if not _is_valid_iframe(url):
            continue

        discovered.add(url)

        if len(discovered) >= MAX_IFRAMES:
            break


    # ---------------------------------------------------------
    # Script scanning fallback
    # ---------------------------------------------------------

    script_urls = _extract_iframes_from_scripts(html)

    for url in script_urls:

        url = _normalize_url(base_url, url)

        if not url:
            continue

        discovered.add(url)

        if len(discovered) >= MAX_IFRAMES:
            break


    # ---------------------------------------------------------
    # Ranking
    # ---------------------------------------------------------

    ranked: List[Tuple[str, int]] = []

    for url in discovered:
        ranked.append((url, _iframe_score(url)))

    ranked.sort(key=lambda x: x[1], reverse=True)

    results = [url for url, _ in ranked][:MAX_IFRAMES]


    if results:

        logger.debug(
            "iframe_menu_urls_discovered count=%s base=%s",
            len(results),
            base_url,
        )

    return results