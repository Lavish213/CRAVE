from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

from app.services.menu.contracts import (
    CanonicalMenu,
    CanonicalMenuItem,
    CanonicalMenuSection,
    ExtractedMenuItem,
)
from app.services.menu.normalization.fingerprint import build_menu_fingerprint


logger = logging.getLogger(__name__)


MAX_ITEMS = 2000
DEFAULT_SECTION = "Other"
DEFAULT_CURRENCY = "USD"
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 4000

MIN_VALID_ITEMS = 2


@dataclass(frozen=True, slots=True)
class _NormalizedRow:
    name: str
    section: str
    description: Optional[str]
    price_cents: Optional[int]
    currency: str
    fingerprint: str
    confidence: float


# ---------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------

def process_extracted_menu(
    items: List[ExtractedMenuItem],
) -> CanonicalMenu:

    if not items:
        logger.info("menu_pipeline_empty_input")
        return CanonicalMenu(sections=[], item_count=0)

    normalized_rows: list[_NormalizedRow] = []
    seen_fingerprints: set[str] = set()

    for raw_item in items[:MAX_ITEMS]:
        try:
            row = _normalize_extracted_item(raw_item)
        except Exception as exc:
            logger.debug("normalize_failed error=%s", exc)
            continue

        if row is None:
            continue

        if row.fingerprint in seen_fingerprints:
            continue

        seen_fingerprints.add(row.fingerprint)
        normalized_rows.append(row)

    # -------------------------------------------------
    # QUALITY GATE
    # -------------------------------------------------

    if len(normalized_rows) < MIN_VALID_ITEMS:
        logger.warning(
            "menu_pipeline_rejected reason=too_small count=%s",
            len(normalized_rows),
        )
        return CanonicalMenu(sections=[], item_count=0)

    if _is_low_quality(normalized_rows):
        logger.warning("menu_pipeline_rejected reason=low_quality")
        return CanonicalMenu(sections=[], item_count=0)

    # -------------------------------------------------
    # SORT
    # -------------------------------------------------

    normalized_rows.sort(
        key=lambda row: (
            row.section.lower(),
            row.name.lower(),
            row.price_cents if row.price_cents is not None else 10**12,
        )
    )

    # -------------------------------------------------
    # GROUP
    # -------------------------------------------------

    grouped: dict[str, list[CanonicalMenuItem]] = defaultdict(list)

    for row in normalized_rows:
        grouped[row.section].append(
            CanonicalMenuItem(
                fingerprint=row.fingerprint,  # 🔥 CRITICAL FIX
                name=row.name,
                section=row.section,
                price_cents=row.price_cents,
                currency=row.currency,
                description=row.description,
                confidence_score=row.confidence,
            )
        )

    sections: list[CanonicalMenuSection] = []

    for section_name in sorted(grouped.keys(), key=lambda v: v.lower()):
        section_items = grouped[section_name]

        sections.append(
            CanonicalMenuSection(
                name=section_name,
                items=section_items,
            )
        )

    menu = CanonicalMenu(
        sections=sections,
        item_count=len(normalized_rows),
    )

    logger.info(
        "menu_pipeline_complete input=%s output=%s sections=%s",
        len(items),
        menu.item_count,
        len(sections),
    )

    return menu


# ---------------------------------------------------------
# QUALITY
# ---------------------------------------------------------

def _is_low_quality(rows: list[_NormalizedRow]) -> bool:
    names = set()
    priced = 0

    for row in rows:
        name = (row.name or "").lower()

        if not name:
            continue

        if name in {"menu", "home", "contact", "order", "about", "login"}:
            continue

        names.add(name)

        if row.price_cents and row.price_cents > 0:
            priced += 1

    if len(names) < MIN_VALID_ITEMS:
        return True

    if len(rows) >= 4 and priced == 0:
        return True

    return False


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------

def _normalize_extracted_item(
    item: ExtractedMenuItem,
) -> Optional[_NormalizedRow]:

    name = _clean_text(getattr(item, "name", None), max_length=MAX_NAME_LENGTH)
    if not name:
        return None

    section = (
        _clean_text(getattr(item, "section", None), max_length=255)
        or DEFAULT_SECTION
    )

    description = _clean_text(
        getattr(item, "description", None),
        max_length=MAX_DESCRIPTION_LENGTH,
    )

    price_cents = _extract_price_cents(item)

    currency = (
        _clean_text(getattr(item, "currency", None), max_length=16)
        or DEFAULT_CURRENCY
    ).upper()

    confidence = _compute_confidence(name, price_cents, description)

    # 🔥 FIXED: NO PRICE IN FINGERPRINT
    fingerprint = build_menu_fingerprint(
        name=name,
        section=section,
        currency=currency,
    )

    return _NormalizedRow(
        name=name,
        section=section,
        description=description,
        price_cents=price_cents,
        currency=currency,
        fingerprint=fingerprint,
        confidence=confidence,
    )


# ---------------------------------------------------------
# CONFIDENCE
# ---------------------------------------------------------

def _compute_confidence(
    name: str,
    price_cents: Optional[int],
    description: Optional[str],
) -> float:

    score = 0.5

    if name:
        score += 0.2
    if price_cents is not None:
        score += 0.2
    if description:
        score += 0.1

    return min(score, 1.0)


# ---------------------------------------------------------
# PRICE
# ---------------------------------------------------------

def _extract_price_cents(item: ExtractedMenuItem) -> Optional[int]:
    price_cents = getattr(item, "price_cents", None)

    if price_cents is not None:
        try:
            cents = int(price_cents)
            return cents if cents >= 0 else None
        except Exception:
            pass

    return _coerce_price_to_cents(getattr(item, "price", None))


def _coerce_price_to_cents(value: object) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if value < 0:
            return None
        return int(round(value * 100)) if value < 1000 else int(value)

    text_value = _clean_text(value)
    if not text_value:
        return None

    cleaned = re.sub(r"[^0-9.\-]", "", text_value)

    try:
        numeric = float(cleaned)
    except Exception:
        return None

    if numeric < 0:
        return None

    return int(round(numeric * 100))


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _clean_text(value: object, *, max_length: int = 255) -> Optional[str]:
    if value is None:
        return None

    try:
        text = str(value).strip()
    except Exception:
        return None

    if not text:
        return None

    text = re.sub(r"\s+", " ", text)
    return text[:max_length].strip()