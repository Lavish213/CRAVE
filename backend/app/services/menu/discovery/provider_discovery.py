from __future__ import annotations

import re
import logging
from typing import List, Set


logger = logging.getLogger(__name__)


_PROVIDER_DOMAINS = [
    "toasttab.com",
    "squareup.com",
    "square.site",
    "popmenu.com",
    "chownow.com",
    "olo.com",
]
# Excluded: clover.com (homepage only, no extractable menu path),
#           grubhub/doordash/ubereats (aggregators — separate pipeline)

# Keywords that indicate a link is menu/order relevant (for JSON-LD fallback hint)
_MENU_LINK_KEYWORDS = ("menu", "order", "food", "eat")

_LINK_REGEX = re.compile(
    r'href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


_IFRAME_REGEX = re.compile(
    r'<iframe[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


_SCRIPT_REGEX = re.compile(
    r'src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Raw HTML scan — catches provider URLs embedded in inline JS, data attrs,
# JSON blobs, etc. that attribute regexes miss.
_RAW_PROVIDER_RE = re.compile(
    r'https?://[^\s\'"<>\\]+(?:'
    + "|".join(re.escape(d) for d in _PROVIDER_DOMAINS)
    + r')[^\s\'"<>\\]*',
    re.IGNORECASE,
)


def _is_provider_url(url: str) -> bool:
    url = url.lower()
    for domain in _PROVIDER_DOMAINS:
        if domain in url:
            return True
    return False


def discover_provider_urls(html: str) -> List[str]:
    """
    Discover external ordering platforms from HTML.

    Scans: href attrs, iframe src, script src, AND raw HTML text
    (catches providers embedded in inline JS / JSON / data attributes).
    """
    found: Set[str] = set()

    try:
        for match in _LINK_REGEX.findall(html):
            if _is_provider_url(match):
                found.add(match)

        for match in _IFRAME_REGEX.findall(html):
            if _is_provider_url(match):
                found.add(match)

        for match in _SCRIPT_REGEX.findall(html):
            if _is_provider_url(match):
                found.add(match)

        # Raw scan — catches URLs in inline JS, data-* attrs, JSON config blobs
        for match in _RAW_PROVIDER_RE.findall(html):
            found.add(match)

    except Exception as exc:
        logger.debug("provider_discovery_failed error=%s", exc)

    results = list(found)
    logger.debug("provider_urls_discovered count=%s", len(results))
    return results


def discover_menu_hint_urls(html: str) -> List[str]:
    """
    Return relative/absolute href links that look menu/order-related.
    Used to find candidate paths for JSON-LD fallback probing.
    """
    hints: Set[str] = set()
    try:
        for match in _LINK_REGEX.findall(html):
            lower = match.lower()
            if any(kw in lower for kw in _MENU_LINK_KEYWORDS):
                # Skip social, admin, login
                if any(x in lower for x in ("facebook", "instagram", "twitter", "login", "admin", "dashboard")):
                    continue
                hints.add(match)
    except Exception:
        pass
    return list(hints)