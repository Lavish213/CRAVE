from __future__ import annotations

import re
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse


# ---------------------------------------------------------
# KEYWORDS (HIGH SIGNAL)
# ---------------------------------------------------------

MENU_KEYWORDS = (
    "menu",
    "menus",
    "food",
    "dining",
    "eat",
    "order",
    "ordering",
    "lunch",
    "dinner",
)

PROVIDER_KEYWORDS = (
    "toasttab",
    "square",
    "chownow",
    "popmenu",
    "clover",
    "olo",
)


# ---------------------------------------------------------
# REGEX
# ---------------------------------------------------------

HREF_REGEX = re.compile(
    r'href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _is_valid_url(url: str) -> bool:
    if not url:
        return False

    url = url.strip()

    if not url:
        return False

    if url.startswith("#"):
        return False

    if url.startswith(("mailto:", "tel:", "javascript:")):
        return False

    return True


def _normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)

        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path or ""

        return f"{scheme}://{netloc}{path}".rstrip("/")

    except Exception:
        return url


def _is_same_domain(base_url: str, candidate: str) -> bool:
    try:
        base_domain = urlparse(base_url).netloc.lower().replace("www.", "")
        candidate_domain = urlparse(candidate).netloc.lower().replace("www.", "")
        return base_domain == candidate_domain
    except Exception:
        return False


def _is_menu_like(url: str) -> bool:
    lower = url.lower()

    return any(k in lower for k in MENU_KEYWORDS) or any(p in lower for p in PROVIDER_KEYWORDS)


def _score(url: str) -> int:
    lower = url.lower()

    score = 0

    if "/menu" in lower:
        score += 5

    if "/order" in lower:
        score += 4

    for p in PROVIDER_KEYWORDS:
        if p in lower:
            score += 4

    for k in MENU_KEYWORDS:
        if k in lower:
            score += 2

    return score


# ---------------------------------------------------------
# CORE FUNCTION
# ---------------------------------------------------------

def find_menu_links(
    html: str,
    base_url: str,
    max_links: int = 20,
) -> List[str]:
    """
    FAST lightweight link finder.

    Purpose:
    • quick signal extraction before deep discovery
    • no BS4 dependency
    • deterministic + ranked

    Guarantees:
    • same-domain only
    • deduplicated
    • ranked (best first)
    """

    if not html or not base_url:
        return []

    found: Set[str] = set()
    scored: List[Tuple[int, str]] = []

    try:
        matches = HREF_REGEX.findall(html)
    except Exception:
        return []

    for href in matches:

        if not _is_valid_url(href):
            continue

        try:
            absolute = urljoin(base_url, href)
        except Exception:
            continue

        absolute = _normalize_url(absolute)

        if not absolute:
            continue

        if not _is_same_domain(base_url, absolute):
            continue

        if not _is_menu_like(absolute):
            continue

        if absolute in found:
            continue

        found.add(absolute)

        scored.append((_score(absolute), absolute))

    # 🔥 deterministic ranking
    scored.sort(key=lambda x: (-x[0], x[1]))

    return [url for _, url in scored[:max_links]]