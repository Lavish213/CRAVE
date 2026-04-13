from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from app.services.menu.contracts import (
    CanonicalMenu,
    CanonicalMenuItem,
    CanonicalMenuSection,
    ExtractedMenuItem,
)

logger = logging.getLogger(__name__)

MAX_ITEMS = 2000
DEFAULT_SECTION = "Other"
DEFAULT_CURRENCY = "USD"
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 4000

MIN_VALID_ITEMS = 2
MIN_NAME_LENGTH = 2

LOW_SIGNAL_NAMES = {
    "menu",
    "home",
    "contact",
    "order",
    "about",
    "login",
    "signup",
    "sign up",
    "register",
    "checkout",
    "cart",
}

NON_MENU_EXACT_NAMES = {
    "napkins",
    "spoons",
    "forks",
    "knives",
    "plates",
    "straws",
    "utensils",
}

NON_MENU_NAME_PATTERNS = [
    r"\bpacket\b",
    r"\bsauce packet\b",
    r"\bextra napkins\b",
    r"\bcutlery\b",
    r"\butensils?\b",
]

SECTION_NORMALIZATION_MAP = {
    "appetizer": "Appetizers",
    "appetizers": "Appetizers",
    "starter": "Appetizers",
    "starters": "Appetizers",
    "breakfast": "Breakfast",
    "desayuno": "Breakfast",
    "burgers": "Burgers",
    "pizza": "Pizza",
    "pizzas": "Pizza",
    "wings": "Wings",
    "sandwich": "Sandwiches",
    "sandwiches": "Sandwiches",
    "fries": "Sides",
    "sides": "Sides",
    "dessert": "Desserts",
    "desserts": "Desserts",
    "drinks": "Drinks",
    "beverages": "Drinks",
}


@dataclass(frozen=True, slots=True)
class _NormalizedRow:
    name: str
    section: str
    description: Optional[str]
    price_cents: Optional[int]
    currency: str
    fingerprint: str
    confidence: float


def process_extracted_menu(
    items: Iterable[ExtractedMenuItem],
) -> CanonicalMenu:
    raw_items = list(items or [])

    if not raw_items:
        logger.info("menu_pipeline_empty_input")
        return CanonicalMenu(sections=[], item_count=0)

    normalized_rows: list[_NormalizedRow] = []
    seen_fingerprints: set[str] = set()

    for raw_item in raw_items[:MAX_ITEMS]:
        try:
            row = _normalize_extracted_item(raw_item)
        except Exception as exc:
            logger.debug("menu_normalize_failed error=%s", exc)
            continue

        if row is None:
            continue

        if row.fingerprint in seen_fingerprints:
            continue

        seen_fingerprints.add(row.fingerprint)
        normalized_rows.append(row)

    if len(normalized_rows) < MIN_VALID_ITEMS:
        logger.warning(
            "menu_pipeline_rejected reason=too_small count=%s",
            len(normalized_rows),
        )
        return CanonicalMenu(sections=[], item_count=0)

    if _is_low_quality(normalized_rows):
        logger.warning("menu_pipeline_rejected reason=low_quality")
        return CanonicalMenu(sections=[], item_count=0)

    normalized_rows.sort(
        key=lambda row: (
            row.section.lower(),
            row.name.lower(),
            row.price_cents if row.price_cents is not None else 10**12,
        )
    )

    grouped: dict[str, list[CanonicalMenuItem]] = defaultdict(list)

    for row in normalized_rows:
        grouped[row.section].append(
            CanonicalMenuItem(
                name=row.name,
                section=row.section,
                price_cents=row.price_cents,
                currency=row.currency,
                description=row.description,
                confidence=row.confidence,
            )
        )

    sections: list[CanonicalMenuSection] = []

    for section_name in sorted(grouped.keys(), key=lambda v: v.lower()):
        section_items = sorted(
            grouped[section_name],
            key=lambda item: (
                (item.name or "").lower(),
                item.price_cents if item.price_cents is not None else 10**12,
            ),
        )

        try:
            sections.append(
                CanonicalMenuSection(
                    name=section_name,
                    items=section_items,
                )
            )
        except TypeError:
            sections.append(
                CanonicalMenuSection(
                    name=section_name,
                    items=section_items,
                    order=len(sections) + 1,
                )
            )

    menu = CanonicalMenu(
        sections=sections,
        item_count=len(normalized_rows),
    )

    logger.info(
        "menu_pipeline_complete input=%s output=%s sections=%s",
        len(raw_items),
        menu.item_count,
        len(sections),
    )

    return menu


def _is_low_quality(rows: list[_NormalizedRow]) -> bool:
    distinct_names: set[str] = set()
    priced = 0
    meaningful_descriptions = 0

    for row in rows:
        name = (row.name or "").strip().lower()
        if not name:
            continue

        if name in LOW_SIGNAL_NAMES:
            continue

        if _looks_like_non_menu_name(name):
            continue

        distinct_names.add(name)

        if row.price_cents is not None and row.price_cents > 0:
            priced += 1

        if row.description and len(row.description.strip()) >= 8:
            meaningful_descriptions += 1

    if len(distinct_names) < MIN_VALID_ITEMS:
        return True

    if len(rows) >= 4 and priced == 0:
        return True

    if len(rows) >= 8 and len(distinct_names) <= 2:
        return True

    if len(rows) >= 10 and priced <= 1 and meaningful_descriptions == 0:
        return True

    return False


def _normalize_extracted_item(
    item: ExtractedMenuItem,
) -> Optional[_NormalizedRow]:
    name = _clean_name(getattr(item, "name", None))
    if not name:
        return None

    if _looks_like_non_menu_name(name):
        return None

    section = _normalize_section(
        _clean_text(getattr(item, "section", None), max_length=255)
    )

    description = _clean_description(
        _clean_text(
            getattr(item, "description", None),
            max_length=MAX_DESCRIPTION_LENGTH,
        )
    )

    price_cents = _extract_price_cents(item)

    currency = (
        _clean_text(getattr(item, "currency", None), max_length=16)
        or DEFAULT_CURRENCY
    ).upper()

    confidence = _compute_confidence(
        name=name,
        section=section,
        price_cents=price_cents,
        description=description,
    )

    fingerprint = _fingerprint(
        name=name,
        section=section,
        price_cents=price_cents,
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


def _compute_confidence(
    *,
    name: str,
    section: str,
    price_cents: Optional[int],
    description: Optional[str],
) -> float:
    score = 0.35

    if name and len(name) >= 3:
        score += 0.20

    if section and section != DEFAULT_SECTION:
        score += 0.10

    if price_cents is not None and price_cents >= 0:
        score += 0.20

    if description and len(description) >= 12:
        score += 0.10

    lowered = name.lower()

    if lowered in NON_MENU_EXACT_NAMES:
        score -= 0.35

    if _looks_like_non_menu_name(lowered):
        score -= 0.30

    if lowered in LOW_SIGNAL_NAMES:
        score -= 0.30

    return max(0.0, min(score, 1.0))


def _extract_price_cents(
    item: ExtractedMenuItem,
) -> Optional[int]:
    price_cents = getattr(item, "price_cents", None)

    if price_cents is not None:
        try:
            cents = int(price_cents)
            return cents if cents >= 0 else None
        except Exception:
            pass

    for attr_name in (
        "base_price_cents",
        "min_price_cents",
        "max_price_cents",
    ):
        raw = getattr(item, attr_name, None)
        if raw is not None:
            try:
                cents = int(raw)
                if cents >= 0:
                    return cents
            except Exception:
                continue

    price = getattr(item, "price", None)
    return _coerce_price_to_cents(price)


def _coerce_price_to_cents(value: object) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, int):
        if value < 0:
            return None
        return value

    if isinstance(value, float):
        if value < 0:
            return None
        return int(round(value * 100))

    text_value = _clean_text(value)
    if not text_value:
        return None

    cleaned = re.sub(r"[^0-9.\-]", "", text_value)

    if not cleaned or cleaned in {"-", ".", "-."}:
        return None

    try:
        numeric = float(cleaned)
    except Exception:
        return None

    if numeric < 0:
        return None

    return int(round(numeric * 100))


def _clean_name(value: object) -> Optional[str]:
    text = _clean_text(value, max_length=MAX_NAME_LENGTH)
    if not text:
        return None

    text = re.sub(r"\s+", " ", text).strip()

    if len(text) < MIN_NAME_LENGTH:
        return None

    return text


def _clean_description(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    cleaned = re.sub(r"\s+", " ", value).strip()

    if not cleaned:
        return None

    return cleaned[:MAX_DESCRIPTION_LENGTH]


def _normalize_section(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_SECTION

    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return DEFAULT_SECTION

    key = cleaned.lower()
    canonical = SECTION_NORMALIZATION_MAP.get(key)

    if canonical:
        return canonical

    return cleaned[:255]


def _looks_like_non_menu_name(name: str) -> bool:
    lowered = (name or "").strip().lower()
    if not lowered:
        return True

    if lowered in NON_MENU_EXACT_NAMES:
        return True

    for pattern in NON_MENU_NAME_PATTERNS:
        if re.search(pattern, lowered):
            return True

    return False


def _clean_text(
    value: object,
    *,
    max_length: int = 255,
) -> Optional[str]:
    if value is None:
        return None

    try:
        text = str(value).strip()
    except Exception:
        return None

    if not text:
        return None

    text = re.sub(r"\s+", " ", text)
    text = text[:max_length].strip()

    return text or None


def _fingerprint(
    *,
    name: str,
    section: str,
    price_cents: Optional[int],
    currency: str,
) -> str:
    raw = "|".join(
        [
            name.lower(),
            section.lower(),
            "" if price_cents is None else str(price_cents),
            currency.upper(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()