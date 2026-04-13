from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Limits
# ---------------------------------------------------------

MAX_ITEMS_ALLOWED = 1500
MIN_REASONABLE_ITEMS = 2


# ---------------------------------------------------------
# Extractor priority
# ---------------------------------------------------------

EXTRACTOR_PRIORITY = {
    "api": 1.20,
    "graphql": 1.15,
    "provider": 1.05,
    "iframe": 0.98,
    "jsonld": 0.92,
    "hydration": 0.88,
    "html": 0.78,
    "pdf": 0.60,
}


# ---------------------------------------------------------
# Junk detection
# ---------------------------------------------------------

NAVIGATION_WORDS = {
    "home",
    "about",
    "contact",
    "locations",
    "location",
    "login",
    "sign in",
    "account",
    "register",
    "menu",
    "menus",
    "order",
    "delivery",
}


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _normalize_items(value: Any) -> List[ExtractedMenuItem]:

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if hasattr(value, "items"):
        try:
            items = getattr(value, "items")
            if isinstance(items, list):
                return items
        except Exception:
            return []

    return []


def _safe_name(item: ExtractedMenuItem) -> str:

    try:
        return (item.name or "").strip().lower()
    except Exception:
        return ""


def _safe_section(item: ExtractedMenuItem) -> str:

    try:
        return (item.section or "").strip().lower()
    except Exception:
        return ""


def _unique_ratio(items: List[ExtractedMenuItem]) -> float:

    if not items:
        return 0.0

    seen = set()

    for item in items:

        name = _safe_name(item)

        if name:
            seen.add(name)

    return len(seen) / len(items)


def _price_ratio(items: List[ExtractedMenuItem]) -> float:

    if not items:
        return 0.0

    priced = 0

    for item in items:

        price = getattr(item, "price", None)

        if price:
            priced += 1

    return priced / len(items)


def _section_ratio(items: List[ExtractedMenuItem]) -> float:

    if not items:
        return 0.0

    sectioned = 0

    for item in items:

        if getattr(item, "section", None):
            sectioned += 1

    return sectioned / len(items)


def _distinct_sections(items: List[ExtractedMenuItem]) -> int:

    sections = {_safe_section(item) for item in items if _safe_section(item)}
    return len(sections)


def _avg_name_length(items: List[ExtractedMenuItem]) -> float:

    if not items:
        return 0.0

    total = 0
    count = 0

    for item in items:

        name = getattr(item, "name", "") or ""

        total += len(name)
        count += 1

    if count == 0:
        return 0.0

    return total / count


def _navigation_ratio(items: List[ExtractedMenuItem]) -> float:

    if not items:
        return 0.0

    nav_hits = 0

    for item in items:

        name = _safe_name(item)

        if name in NAVIGATION_WORDS:
            nav_hits += 1

    return nav_hits / len(items)


def _name_entropy(items: List[ExtractedMenuItem]) -> float:

    if not items:
        return 0.0

    names = [_safe_name(i) for i in items if _safe_name(i)]

    if not names:
        return 0.0

    unique = len(set(names))

    return unique / len(names)


def _price_format_sanity(items: List[ExtractedMenuItem]) -> float:

    """
    Detect strange price outputs like:
    $111111111111
    $999999
    """

    if not items:
        return 0.0

    good = 0

    for item in items:

        price = getattr(item, "price", None)

        if not price:
            continue

        if len(str(price)) <= 12:
            good += 1

    return good / len(items)


# ---------------------------------------------------------
# Score calculation
# ---------------------------------------------------------

def _score_result(result: Dict[str, Any]) -> float:

    raw_items = result.get("items", [])
    items = _normalize_items(raw_items)
    extractor = result.get("extractor")

    if not items:
        return 0.0

    count = len(items)

    if count > MAX_ITEMS_ALLOWED:
        logger.debug("menu_rank_reject_too_large count=%s", count)
        return 0.0

    if count < MIN_REASONABLE_ITEMS:
        logger.debug("menu_rank_reject_too_small count=%s", count)
        return 0.0

    score = 0.0


    # -----------------------------------------------------
    # extractor reliability
    # -----------------------------------------------------

    score += EXTRACTOR_PRIORITY.get(extractor, 0.50)


    # -----------------------------------------------------
    # item count signal
    # -----------------------------------------------------

    if count >= 120:
        score += 0.55
    elif count >= 80:
        score += 0.50
    elif count >= 50:
        score += 0.45
    elif count >= 30:
        score += 0.35
    elif count >= 20:
        score += 0.30
    elif count >= 10:
        score += 0.20
    elif count >= 5:
        score += 0.10


    # -----------------------------------------------------
    # duplicate detection
    # -----------------------------------------------------

    unique_ratio = _unique_ratio(items)
    score += unique_ratio * 0.35


    # -----------------------------------------------------
    # price presence
    # -----------------------------------------------------

    price_ratio = _price_ratio(items)
    score += price_ratio * 0.45


    # -----------------------------------------------------
    # price sanity
    # -----------------------------------------------------

    price_sanity = _price_format_sanity(items)
    score += price_sanity * 0.15


    # -----------------------------------------------------
    # section structure
    # -----------------------------------------------------

    section_ratio = _section_ratio(items)
    score += section_ratio * 0.22

    distinct_sections = _distinct_sections(items)

    if distinct_sections >= 6:
        score += 0.20
    elif distinct_sections >= 4:
        score += 0.15
    elif distinct_sections >= 2:
        score += 0.08


    # -----------------------------------------------------
    # name sanity
    # -----------------------------------------------------

    avg_len = _avg_name_length(items)

    if 4 <= avg_len <= 60:
        score += 0.10
    elif avg_len < 2:
        score -= 0.35


    # -----------------------------------------------------
    # navigation penalty
    # -----------------------------------------------------

    nav_ratio = _navigation_ratio(items)

    if nav_ratio > 0.5:
        score -= 0.90
    elif nav_ratio > 0.3:
        score -= 0.60


    # -----------------------------------------------------
    # entropy penalty (garbage detection)
    # -----------------------------------------------------

    entropy = _name_entropy(items)

    if entropy < 0.2:
        score -= 0.70
    elif entropy < 0.3:
        score -= 0.45


    if score < 0:
        score = 0.0

    if score > 3.5:
        score = 3.5

    return score


# ---------------------------------------------------------
# Public ranking
# ---------------------------------------------------------

def rank_extraction_results(
    results: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:

    if not results:
        return None

    scored: List[tuple[float, Dict[str, Any], int]] = []

    for idx, result in enumerate(results):

        try:

            score = _score_result(result)

            if score <= 0:
                continue

            scored.append((score, result, idx))

        except Exception as exc:

            logger.debug(
                "extraction_score_failed error=%s",
                exc,
            )

    if not scored:
        return None

    scored.sort(key=lambda x: (x[0], -x[2]), reverse=True)

    best_score, best_result, _ = scored[0]
    best_items = _normalize_items(best_result.get("items", []))

    logger.info(
        "menu_extraction_selected extractor=%s items=%s score=%.3f",
        best_result.get("extractor"),
        len(best_items),
        best_score,
    )

    return {
        **best_result,
        "items": best_items,
    }