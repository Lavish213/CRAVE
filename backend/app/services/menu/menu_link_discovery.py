# FILE: backend/app/services/menu/menu_link_discovery.py

from __future__ import annotations

import logging
import re
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse, urldefrag

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


MAX_LINKS = 75


MENU_KEYWORDS = [
    "menu",
    "menus",
    "order",
    "ordering",
    "food",
    "eat",
    "dinner",
    "lunch",
    "breakfast",
    "takeout",
    "delivery",
    "online-order",
    "order-online",
    "our-menu",
    "food-menu",
]

PROVIDER_KEYWORDS = [
    "toasttab",
    "square",
    "squareup",
    "square.site",
    "clover",
    "chownow",
    "olo",
    "popmenu",
    "spoton",
    "menufy",
    "order.online",
]

BAD_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".css",
    ".js",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".map",
    ".xml",
    ".zip",
)

MENU_FILE_PATTERN = re.compile(
    r"\.(pdf|html|php|menu)(?:\?.*)?$",
    re.IGNORECASE,
)

HREF_PATTERN = re.compile(
    r'href\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

SCRIPT_URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+",
    re.IGNORECASE,
)

SPA_ROUTE_PATTERN = re.compile(
    r'["\'](/[^"\']*(?:menu|order|food)[^"\']*)["\']',
    re.IGNORECASE,
)

BUTTON_ROUTE_PATTERN = re.compile(
    r'["\'](/[^"\']+)["\']',
    re.IGNORECASE,
)


def _clean_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    url, _ = urldefrag(url)
    return url.rstrip("/")


def _root_domain(netloc: str) -> str:
    host = (netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_url(base_url: str, href: str | None) -> str | None:
    if not href:
        return None

    href = _clean_url(href)
    if not href:
        return None

    lowered = href.lower()

    if href.startswith("#"):
        return None

    if lowered.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return None

    try:
        url = urljoin(base_url, href)
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return None

        normalized = _clean_url(url)
        if not normalized:
            return None

        return normalized

    except Exception:
        return None


def _has_bad_extension(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()

    if MENU_FILE_PATTERN.search(url):
        return False

    return any(path.endswith(ext) for ext in BAD_EXTENSIONS)


def _same_domain(base_url: str, candidate_url: str) -> bool:
    try:
        base_domain = _root_domain(urlparse(base_url).netloc)
        candidate_domain = _root_domain(urlparse(candidate_url).netloc)

        if not base_domain or not candidate_domain:
            return False

        return (
            candidate_domain == base_domain
            or candidate_domain.endswith("." + base_domain)
            or base_domain.endswith("." + candidate_domain)
        )
    except Exception:
        return False


def _looks_like_menu_link(url: str) -> bool:
    url_lower = url.lower()

    if _has_bad_extension(url):
        return False

    if MENU_FILE_PATTERN.search(url_lower):
        return True

    for keyword in MENU_KEYWORDS:
        if keyword in url_lower:
            return True

    for provider in PROVIDER_KEYWORDS:
        if provider in url_lower:
            return True

    return False


def _score_menu_link(url: str, base_url: str) -> int:
    url_lower = url.lower()
    score = 0

    if _same_domain(base_url, url):
        score += 3

    if "/menu" in url_lower:
        score += 8

    if "/menus" in url_lower:
        score += 6

    if "/order" in url_lower or "/ordering" in url_lower:
        score += 5

    if MENU_FILE_PATTERN.search(url_lower):
        score += 5

    for provider in PROVIDER_KEYWORDS:
        if provider in url_lower:
            score += 6  # 🔥 increased weight (providers are gold)

    for keyword in MENU_KEYWORDS:
        if keyword in url_lower:
            score += 2

    return score


def _extract_urls_from_scripts(html: str) -> List[str]:
    urls: List[str] = []

    for url in SCRIPT_URL_PATTERN.findall(html):
        if _looks_like_menu_link(url):
            urls.append(url)

    return urls


def _extract_spa_routes(html: str, base_url: str) -> List[str]:
    routes: List[str] = []

    for route in SPA_ROUTE_PATTERN.findall(html):
        url = _normalize_url(base_url, route)

        if not url:
            continue

        if _looks_like_menu_link(url):
            routes.append(url)

    return routes


def _extract_href_links_regex(html: str) -> List[str]:
    return HREF_PATTERN.findall(html)


def _add_url(discovered: Set[str], url: str, base_url: str) -> None:
    clean = _clean_url(url)

    if not clean:
        return

    if not _same_domain(base_url, clean):
        return

    if not _looks_like_menu_link(clean):
        return

    discovered.add(clean)


def discover_menu_links(
    html: str,
    base_url: str,
) -> List[str]:
    if not html or not base_url:
        return []

    discovered: Set[str] = set()

    try:
        soup = BeautifulSoup(html, "html.parser")

        # -------------------------
        # STANDARD TAGS
        # -------------------------

        for tag_name, attr in [
            ("a", "href"),
            ("iframe", "src"),
            ("link", "href"),
        ]:
            for tag in soup.find_all(tag_name):
                url = _normalize_url(base_url, tag.get(attr))
                if not url:
                    continue

                _add_url(discovered, url, base_url)

                if len(discovered) >= MAX_LINKS:
                    break

        # -------------------------
        # DATA ATTRS
        # -------------------------

        for attr in ("data-url", "data-href"):
            for tag in soup.find_all(attrs={attr: True}):
                url = _normalize_url(base_url, tag.get(attr))
                if not url:
                    continue

                _add_url(discovered, url, base_url)

                if len(discovered) >= MAX_LINKS:
                    break

        # -------------------------
        # BUTTONS / ONCLICK
        # -------------------------

        for button in soup.find_all("button"):
            for attr in ("data-url", "data-href", "onclick"):
                val = button.get(attr)

                if not val:
                    continue

                match = BUTTON_ROUTE_PATTERN.search(val)

                if not match:
                    continue

                url = _normalize_url(base_url, match.group(1))
                if not url:
                    continue

                _add_url(discovered, url, base_url)

                if len(discovered) >= MAX_LINKS:
                    break

            if len(discovered) >= MAX_LINKS:
                break

        # -------------------------
        # SCRIPT URLS
        # -------------------------

        for url in _extract_urls_from_scripts(html):
            _add_url(discovered, url, base_url)

            if len(discovered) >= MAX_LINKS:
                break

        # -------------------------
        # SPA ROUTES
        # -------------------------

        if len(discovered) < MAX_LINKS:
            for url in _extract_spa_routes(html, base_url):
                _add_url(discovered, url, base_url)

                if len(discovered) >= MAX_LINKS:
                    break

    except Exception as exc:
        logger.debug("menu_link_discovery_bs4_failed error=%s", exc)

        try:
            for href in _extract_href_links_regex(html):
                url = _normalize_url(base_url, href)
                if not url:
                    continue

                _add_url(discovered, url, base_url)

                if len(discovered) >= MAX_LINKS:
                    break

        except Exception as exc2:
            logger.debug("menu_link_discovery_regex_failed error=%s", exc2)

    # -------------------------
    # FINAL RANK + CLEAN
    # -------------------------

    ranked: List[Tuple[str, int]] = [
        (url, _score_menu_link(url, base_url))
        for url in discovered
    ]

    ranked.sort(key=lambda item: (-item[1], item[0]))

    # 🔥 FINAL FILTER (anti-garbage)
    final: List[str] = []
    seen: Set[str] = set()

    for url, _ in ranked:
        if url in seen:
            continue

        seen.add(url)

        # remove obvious junk
        if any(x in url.lower() for x in ("login", "signup", "account")):
            continue

        final.append(url)

        if len(final) >= MAX_LINKS:
            break

    return final