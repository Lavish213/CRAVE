from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from typing import List, Set

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


MAX_LOCATION_LINKS = 200


LOCATION_KEYWORDS = [
    "locations",
    "location",
    "stores",
    "store",
    "restaurants",
    "restaurant",
    "find-us",
    "findus",
    "visit",
]


def _normalize(url: str, href: str) -> str | None:

    if not href:
        return None

    href = href.strip()

    if href.startswith("#"):
        return None

    try:

        full = urljoin(url, href)

        parsed = urlparse(full)

        if parsed.scheme not in ("http", "https"):
            return None

        return full

    except Exception:
        return None


def _looks_like_location(url: str) -> bool:

    url_lower = url.lower()

    for keyword in LOCATION_KEYWORDS:

        if keyword in url_lower:
            return True

    return False


def discover_location_pages(
    html: str,
    base_url: str,
) -> List[str]:

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    discovered: Set[str] = set()

    for a in soup.find_all("a"):

        href = a.get("href")

        url = _normalize(base_url, href)

        if not url:
            continue

        if not _looks_like_location(url):
            continue

        discovered.add(url)

        if len(discovered) >= MAX_LOCATION_LINKS:
            break

    results = list(discovered)

    if results:

        logger.debug(
            "location_pages_discovered count=%s base=%s",
            len(results),
            base_url,
        )

    return results