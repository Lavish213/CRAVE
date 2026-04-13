from __future__ import annotations

import logging
from typing import Optional, List, Tuple, Set
from urllib.parse import urlparse

from .menu_source_types import MenuSourceType


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# BASE PRIORITY
# ---------------------------------------------------------

BASE_SOURCE_PRIORITY = {
    MenuSourceType.PROVIDER_API: 1.2,   # 🔥 strongest
    MenuSourceType.OFFICIAL_HTML: 1.0,
    MenuSourceType.SCRAPED_HTML: 0.75,
    MenuSourceType.PDF: 0.6,
}


# ---------------------------------------------------------
# TRUSTED PROVIDERS (BOOST)
# ---------------------------------------------------------

TRUSTED_PROVIDERS = [
    "toasttab.com",
    "squareup.com",
    "square.site",
    "olo.com",
    "chownow.com",
    "popmenu.com",
    "clover.com",
]


# ---------------------------------------------------------
# DELIVERY (PENALIZE)
# ---------------------------------------------------------

DELIVERY_DOMAINS = [
    "doordash.com",
    "ubereats.com",
    "grubhub.com",
    "postmates.com",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    try:
        parsed = urlparse(url)
        return parsed.geturl().lower().rstrip("/")
    except Exception:
        return url.lower().rstrip("/")


def _extract_domain(url: Optional[str]) -> str:
    try:
        return urlparse(url or "").netloc.lower()
    except Exception:
        return ""


# ---------------------------------------------------------
# SIGNALS
# ---------------------------------------------------------

def _trusted_provider_boost(domain: str) -> float:
    return 0.3 if any(p in domain for p in TRUSTED_PROVIDERS) else 0.0


def _delivery_penalty(domain: str) -> float:
    return -0.5 if any(d in domain for d in DELIVERY_DOMAINS) else 0.0


def _menu_keyword_boost(url: Optional[str]) -> float:
    if not url:
        return 0.0

    u = url.lower()

    score = 0.0

    if "/menu" in u:
        score += 0.2
    if "/order" in u:
        score += 0.15
    if "/food" in u:
        score += 0.1
    if "/dinner" in u or "/lunch" in u:
        score += 0.05

    return score


def _pdf_penalty(source_type: MenuSourceType) -> float:
    return -0.15 if source_type == MenuSourceType.PDF else 0.0


# ---------------------------------------------------------
# MAIN SCORING
# ---------------------------------------------------------

def score_source(
    source_type: MenuSourceType,
    *,
    url: Optional[str] = None,
    base_domain: Optional[str] = None,
) -> float:

    try:

        normalized = _normalize_url(url)
        domain = _extract_domain(normalized)

        score = BASE_SOURCE_PRIORITY.get(source_type, 0.5)

        # provider boost
        score += _trusted_provider_boost(domain)

        # delivery penalty
        score += _delivery_penalty(domain)

        # keyword signals
        score += _menu_keyword_boost(normalized)

        # pdf penalty
        score += _pdf_penalty(source_type)

        # 🔥 SAME DOMAIN BOOST (official site)
        if base_domain and domain == base_domain:
            score += 0.25

        # clamp
        score = max(0.0, min(score, 2.0))

        return score

    except Exception as exc:

        logger.debug(
            "menu_source_score_failed url=%s error=%s",
            url,
            exc,
        )

        return 0.0


# ---------------------------------------------------------
# RANKING
# ---------------------------------------------------------

def rank_sources(
    sources: List[Tuple[MenuSourceType, str]],
    *,
    base_url: Optional[str] = None,
) -> List[Tuple[MenuSourceType, str]]:

    base_domain = _extract_domain(base_url)

    seen: Set[str] = set()
    scored: List[Tuple[float, str, MenuSourceType, str]] = []

    for source_type, url in sources:

        normalized = _normalize_url(url)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)

        score = score_source(
            source_type,
            url=normalized,
            base_domain=base_domain,
        )

        # deterministic tie-breaker → URL
        scored.append((score, normalized, source_type, normalized))

    # sort:
    # 1. score DESC
    # 2. url ASC (deterministic)
    scored.sort(key=lambda x: (-x[0], x[1]))

    ranked = [(stype, url) for _, _, stype, url in scored]

    logger.debug(
        "menu_sources_ranked count=%s",
        len(ranked),
    )

    return ranked