from __future__ import annotations

import logging
import re
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


MAX_DISCOVERED_BUNDLES = 30


INLINE_JS_URL_PATTERN = re.compile(
    r"""(?P<quote>["'])(?P<url>
        (?:
            /_next/static/[^"'\\]+\.js(?:\?[^"'\\]*)? |
            /static/js/[^"'\\]+\.js(?:\?[^"'\\]*)? |
            /assets/[^"'\\]+\.js(?:\?[^"'\\]*)? |
            /build/[^"'\\]+\.js(?:\?[^"'\\]*)? |
            /dist/[^"'\\]+\.js(?:\?[^"'\\]*)? |
            /_nuxt/[^"'\\]+\.js(?:\?[^"'\\]*)? |
            /chunks?/[^"'\\]+\.js(?:\?[^"'\\]*)? |
            /[^"'\\]+\.(?:chunk|bundle|runtime|vendor)\.js(?:\?[^"'\\]*)?
        )
    )(?P=quote)""",
    re.VERBOSE | re.IGNORECASE,
)

DYNAMIC_IMPORT_PATTERN = re.compile(
    r"""import\s*\(\s*(?P<quote>["'])(?P<url>[^"'\\]+\.js(?:\?[^"'\\]*)?)(?P=quote)\s*\)""",
    re.IGNORECASE,
)

WEBPACK_PUSH_PATTERN = re.compile(
    r"""["'](?P<url>[^"'\\]+(?:chunk|bundle|runtime|vendor)[^"'\\]*\.js(?:\?[^"'\\]*)?)["']""",
    re.IGNORECASE,
)

COMMON_BUNDLE_PATH_HINTS = (
    "/_next/static/",
    "/static/js/",
    "/assets/",
    "/build/",
    "/dist/",
    "/_nuxt/",
    "/chunks/",
    "/chunk/",
)

EXCLUDED_SUBSTRINGS = (
    ".json",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
)

EXCLUDED_SCHEMES = (
    "data:",
    "blob:",
    "javascript:",
    "mailto:",
    "tel:",
)


def _strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def _same_host_score(url: str, base_url: Optional[str]) -> int:
    if not base_url:
        return 0

    try:
        a = urlparse(url).netloc.lower()
        b = urlparse(base_url).netloc.lower()

        if a == b:
            return 3

        if a.endswith("." + b) or b.endswith("." + a):
            return 2
    except Exception:
        return 0

    return 0


def _normalize_bundle_url(raw_url: str, base_url: Optional[str]) -> Optional[str]:
    if not raw_url:
        return None

    raw_url = raw_url.strip()

    if not raw_url:
        return None

    lowered = raw_url.lower()

    if lowered.startswith(EXCLUDED_SCHEMES):
        return None

    if any(token in lowered for token in EXCLUDED_SUBSTRINGS):
        return None

    if not lowered.endswith(".js") and ".js?" not in lowered:
        return None

    if raw_url.startswith("//"):
        raw_url = f"https:{raw_url}"

    if raw_url.startswith(("http://", "https://")):
        normalized = raw_url
    elif base_url:
        normalized = urljoin(base_url, raw_url)
    else:
        return None

    normalized = _strip_fragment(normalized)

    parsed = urlparse(normalized)

    if parsed.scheme not in ("http", "https"):
        return None

    if not parsed.netloc:
        return None

    return normalized


def _looks_like_bundle_url(url: str) -> bool:
    lowered = url.lower()

    if not lowered.endswith(".js") and ".js?" not in lowered:
        return False

    if any(token in lowered for token in EXCLUDED_SUBSTRINGS):
        return False

    if any(hint in lowered for hint in COMMON_BUNDLE_PATH_HINTS):
        return True

    if ".chunk." in lowered or ".bundle." in lowered:
        return True

    if ".runtime." in lowered or ".vendor." in lowered:
        return True

    if "/chunks/" in lowered or "/chunk/" in lowered:
        return True

    return True


def _bundle_score(url: str, base_url: Optional[str]) -> int:
    lowered = url.lower()
    score = 0

    score += _same_host_score(url, base_url)

    if "/_next/static/" in lowered:
        score += 8
    if "/_nuxt/" in lowered:
        score += 8
    if "/static/js/" in lowered:
        score += 7
    if "/assets/" in lowered:
        score += 5
    if "/build/" in lowered or "/dist/" in lowered:
        score += 4
    if ".chunk." in lowered:
        score += 6
    if ".bundle." in lowered:
        score += 5
    if ".runtime." in lowered:
        score += 4
    if ".vendor." in lowered:
        score += 4
    if "/chunks/" in lowered or "/chunk/" in lowered:
        score += 5

    return score


def _add_candidate(
    discovered: Set[str],
    raw_url: str,
    base_url: Optional[str],
) -> None:
    normalized = _normalize_bundle_url(raw_url, base_url)

    if not normalized:
        return

    if not _looks_like_bundle_url(normalized):
        return

    discovered.add(normalized)


def _discover_from_script_tags(
    html: str,
    base_url: Optional[str],
    discovered: Set[str],
) -> None:
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script"):
        src = script.get("src")

        if src:
            _add_candidate(discovered, src, base_url)

        data_src = script.get("data-src")
        if data_src:
            _add_candidate(discovered, data_src, base_url)


def _discover_from_link_tags(
    html: str,
    base_url: Optional[str],
    discovered: Set[str],
) -> None:
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("link"):
        href = link.get("href")
        rel = " ".join(link.get("rel", [])).lower()
        as_attr = (link.get("as") or "").lower()

        if not href:
            continue

        if "modulepreload" in rel:
            _add_candidate(discovered, href, base_url)
            continue

        if "preload" in rel and as_attr == "script":
            _add_candidate(discovered, href, base_url)
            continue


def _discover_from_inline_patterns(
    html: str,
    base_url: Optional[str],
    discovered: Set[str],
) -> None:
    for match in INLINE_JS_URL_PATTERN.finditer(html):
        _add_candidate(discovered, match.group("url"), base_url)

    for match in DYNAMIC_IMPORT_PATTERN.finditer(html):
        _add_candidate(discovered, match.group("url"), base_url)

    for match in WEBPACK_PUSH_PATTERN.finditer(html):
        _add_candidate(discovered, match.group("url"), base_url)


def discover_js_bundles(
    html: str,
    base_url: Optional[str],
) -> List[str]:
    """
    Discover candidate JS bundle URLs from a page.

    Sources:
    - <script src>
    - <script data-src>
    - <link rel="modulepreload">
    - <link rel="preload" as="script">
    - inline dynamic imports
    - inline asset string hints from modern frameworks

    Returns a ranked, stable, deduplicated list of normalized bundle URLs.
    """

    if not html:
        return []

    discovered: Set[str] = set()

    try:
        _discover_from_script_tags(html, base_url, discovered)
    except Exception as exc:
        logger.debug("js_bundle_discovery_script_tags_failed error=%s", exc)

    try:
        _discover_from_link_tags(html, base_url, discovered)
    except Exception as exc:
        logger.debug("js_bundle_discovery_link_tags_failed error=%s", exc)

    try:
        _discover_from_inline_patterns(html, base_url, discovered)
    except Exception as exc:
        logger.debug("js_bundle_discovery_inline_patterns_failed error=%s", exc)

    ranked: List[Tuple[int, str]] = []

    for url in discovered:
        ranked.append((_bundle_score(url, base_url), url))

    ranked.sort(key=lambda x: (-x[0], x[1]))

    bundles = [url for _, url in ranked[:MAX_DISCOVERED_BUNDLES]]

    logger.debug(
        "js_bundle_discovery_complete base_url=%s discovered=%s",
        base_url,
        len(bundles),
    )

    return bundles