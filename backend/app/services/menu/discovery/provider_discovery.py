from __future__ import annotations

import re
import logging
from typing import List, Set


logger = logging.getLogger(__name__)


_PROVIDER_DOMAINS = [
    "toasttab.com",
    "squareup.com",
    "square.site",
    "clover.com",
    "popmenu.com",
    "chownow.com",
    "olo.com",
    "doordash.com",
    "ubereats.com",
    "grubhub.com",
]


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


def _is_provider_url(url: str) -> bool:

    url = url.lower()

    for domain in _PROVIDER_DOMAINS:
        if domain in url:
            return True

    return False


def discover_provider_urls(html: str) -> List[str]:
    """
    Discover external ordering platforms from HTML.
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

    except Exception as exc:

        logger.debug(
            "provider_discovery_failed error=%s",
            exc,
        )

    results = list(found)

    logger.debug(
        "provider_urls_discovered count=%s",
        len(results),
    )

    return results