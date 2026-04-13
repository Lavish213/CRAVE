from __future__ import annotations

import logging
import re
from typing import List, Set, Optional, Tuple
from urllib.parse import urljoin, urlparse, urldefrag

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Limits
# ---------------------------------------------------------

MAX_API_ENDPOINTS = 40


# ---------------------------------------------------------
# API / GraphQL patterns
# ---------------------------------------------------------

API_PATH_PATTERNS = [
    "/api/menu",
    "/menu.json",
    "/api/v1/menu",
    "/api/v2/menu",
    "/api/menu-items",
    "/menu-items",
    "/products",
    "/product",
    "/catalog",
    "/graphql",
    "/api/graphql",
    "/menu",
    "/menus",
    "/restaurant",
    "/restaurants",
    "/location",
    "/locations",
    "/ordering",
    "/order",
]


PROVIDER_HINTS = [
    "toasttab",
    "squareup",
    "square.site",
    "clover",
    "chownow",
    "olo",
    "popmenu",
    "spoton",
    "menufy",
    "order.online",
    "gloriafood",
    "lunchbox",
    "bentobox",
]


# ---------------------------------------------------------
# JS request detection
# ---------------------------------------------------------

FETCH_PATTERN = re.compile(
    r"""fetch\(\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

AXIOS_PATTERN = re.compile(
    r"""axios\.(?:get|post|put|request)\(\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

GENERIC_URL_PATTERN = re.compile(
    r"""https?://[^\s"'<>]+""",
    re.IGNORECASE,
)

RELATIVE_API_PATTERN = re.compile(
    r"""["'](\/[^"'<>]*?(?:api|graphql|menu|menus|products|catalog|ordering|order)[^"'<>]*)["']""",
    re.IGNORECASE,
)

GRAPHQL_ASSIGNMENT_PATTERN = re.compile(
    r"""["']([^"']*graphql[^"']*)["']""",
    re.IGNORECASE,
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    url, _ = urldefrag(url)
    return url


def _normalize_url(base_url: str, url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    url = _clean_url(url)
    if not url:
        return None

    try:
        normalized = urljoin(base_url, url)
        parsed = urlparse(normalized)

        if parsed.scheme not in ("http", "https"):
            return None

        return normalized

    except Exception:
        return None


def _looks_like_api(url: str) -> bool:
    url_lower = url.lower()

    if any(pattern in url_lower for pattern in API_PATH_PATTERNS):
        return True

    if "graphql" in url_lower:
        return True

    if any(hint in url_lower for hint in PROVIDER_HINTS):
        return True

    return False


def _endpoint_score(url: str) -> int:
    url_lower = url.lower()
    score = 0

    score += sum(3 for p in API_PATH_PATTERNS if p in url_lower)
    score += 4 if "graphql" in url_lower else 0
    score += sum(5 for h in PROVIDER_HINTS if h in url_lower)
    score += 2 if "menu" in url_lower else 0

    return score


def _add_candidate(
    discovered: Set[str],
    base_url: str,
    raw_url: Optional[str],
) -> None:

    if len(discovered) >= MAX_API_ENDPOINTS:
        return

    url = _normalize_url(base_url, raw_url)

    if not url or not _looks_like_api(url):
        return

    discovered.add(url)


# ---------------------------------------------------------
# Script scanning
# ---------------------------------------------------------

def _scan_scripts(
    soup: BeautifulSoup,
    base_url: str,
    discovered: Set[str],
) -> None:

    for script in soup.find_all("script"):

        if len(discovered) >= MAX_API_ENDPOINTS:
            return

        script_src = script.get("src")
        if script_src:
            _add_candidate(discovered, base_url, script_src)

        text = script.string or script.get_text() or ""
        if not text:
            continue

        for match in FETCH_PATTERN.findall(text):
            _add_candidate(discovered, base_url, match)

        for match in AXIOS_PATTERN.findall(text):
            _add_candidate(discovered, base_url, match)

        for raw in GENERIC_URL_PATTERN.findall(text):
            _add_candidate(discovered, base_url, raw)

        for raw in RELATIVE_API_PATTERN.findall(text):
            _add_candidate(discovered, base_url, raw)

        for raw in GRAPHQL_ASSIGNMENT_PATTERN.findall(text):
            _add_candidate(discovered, base_url, raw)


# ---------------------------------------------------------
# DOM scanning
# ---------------------------------------------------------

def _scan_forms(
    soup: BeautifulSoup,
    base_url: str,
    discovered: Set[str],
) -> None:

    for form in soup.find_all("form"):

        if len(discovered) >= MAX_API_ENDPOINTS:
            return

        action = form.get("action")
        if action:
            _add_candidate(discovered, base_url, action)


def _scan_data_attributes(
    soup: BeautifulSoup,
    base_url: str,
    discovered: Set[str],
) -> None:

    for tag in soup.find_all(True):

        if len(discovered) >= MAX_API_ENDPOINTS:
            return

        for attr_name, attr_value in tag.attrs.items():

            if not isinstance(attr_value, str):
                continue

            attr_name_lower = str(attr_name).lower()
            attr_value_lower = attr_value.lower()

            if "api" in attr_name_lower or "graphql" in attr_name_lower:
                _add_candidate(discovered, base_url, attr_value)

            elif _looks_like_api(attr_value_lower):
                _add_candidate(discovered, base_url, attr_value)


# ---------------------------------------------------------
# Built-in fallback guesses
# ---------------------------------------------------------

def _add_common_fallbacks(
    base_url: str,
    discovered: Set[str],
) -> None:

    fallback_paths = [
        "/api/menu",
        "/menu.json",
        "/graphql",
        "/api/graphql",
        "/api/v1/menu",
        "/api/v2/menu",
        "/api/menu-items",
        "/products",
        "/catalog",
    ]

    for path in fallback_paths:

        if len(discovered) >= MAX_API_ENDPOINTS:
            return

        _add_candidate(discovered, base_url, path)


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def discover_api_endpoints(
    html: str,
    base_url: str,
) -> List[str]:

    if not html or not base_url:
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []

    discovered: Set[str] = set()

    _scan_scripts(soup, base_url, discovered)
    _scan_forms(soup, base_url, discovered)
    _scan_data_attributes(soup, base_url, discovered)
    _add_common_fallbacks(base_url, discovered)

    ranked: List[Tuple[str, int]] = [
        (url, _endpoint_score(url)) for url in discovered
    ]

    ranked.sort(key=lambda x: x[1], reverse=True)

    results = [url for url, _ in ranked][:MAX_API_ENDPOINTS]

    if results:
        logger.info(
            "api_endpoints_discovered count=%s base=%s",
            len(results),
            base_url,
        )

    return results