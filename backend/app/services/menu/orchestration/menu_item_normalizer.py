from __future__ import annotations

import re
import unicodedata
from typing import List

from app.services.menu.contracts import (
    ExtractedMenuItem,
    NormalizedMenuItem,
)

from app.services.menu.normalization.fingerprint import build_menu_fingerprint


# ---------------------------------------------------------
# Regex
# ---------------------------------------------------------

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s/&-]")


# ---------------------------------------------------------
# Section aliases
# ---------------------------------------------------------

_SECTION_ALIASES = {
    "apps": "Appetizers",
    "appetizers": "Appetizers",
    "starter": "Appetizers",
    "starters": "Appetizers",
    "small plates": "Appetizers",

    "mains": "Entrees",
    "main": "Entrees",
    "main dishes": "Entrees",
    "entree": "Entrees",
    "entrees": "Entrees",

    "drinks": "Drinks",
    "drink": "Drinks",
    "beverages": "Drinks",

    "desserts": "Desserts",
    "dessert": "Desserts",

    "burritos": "Burritos",
    "tacos": "Tacos",
    "sandwiches": "Sandwiches",
    "burgers": "Burgers",
    "salads": "Salads",
    "sides": "Sides",
}


# ---------------------------------------------------------
# Unicode normalization
# ---------------------------------------------------------

def _normalize_unicode(text: str) -> str:
    try:
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
    except Exception:
        pass
    return text


# ---------------------------------------------------------
# Cleaning
# ---------------------------------------------------------

def _clean(value: str | None) -> str:
    if not value:
        return ""

    text = value.strip()
    text = _normalize_unicode(text)
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text)

    return text.strip()


# ---------------------------------------------------------
# Name
# ---------------------------------------------------------

def _normalize_name(name: str | None) -> str:
    cleaned = _clean(name)
    return cleaned if cleaned else ""


# ---------------------------------------------------------
# Section
# ---------------------------------------------------------

def _normalize_section(section: str | None) -> str:
    text = _clean(section).lower()

    if not text:
        return "Other"

    if text in _SECTION_ALIASES:
        return _SECTION_ALIASES[text]

    for key, value in _SECTION_ALIASES.items():
        if key in text:
            return value

    return " ".join(part.capitalize() for part in text.split())


# ---------------------------------------------------------
# Currency
# ---------------------------------------------------------

def _normalize_currency(currency: str | None) -> str:
    if not currency:
        return "USD"

    value = currency.strip().upper()
    return value if value else "USD"


# ---------------------------------------------------------
# Description
# ---------------------------------------------------------

def _normalize_description(description: str | None) -> str | None:
    text = _clean(description)

    if not text:
        return None

    if len(text) < 3:
        return None

    if len(text) > 300:
        return text[:300]

    return text


# ---------------------------------------------------------
# SINGLE ITEM NORMALIZATION
# ---------------------------------------------------------

def normalize_menu_item(item: ExtractedMenuItem) -> NormalizedMenuItem:

    name = _normalize_name(item.name) or "Unknown"
    section = _normalize_section(item.section)
    currency = _normalize_currency(item.currency)
    description = _normalize_description(item.description)

    # ---------------- PRICE ----------------
    price_cents = item.price_cents

    if price_cents is not None:
        try:
            price_cents = int(price_cents)
            if price_cents < 0:
                price_cents = None
        except Exception:
            price_cents = None

    # ---------------- FINGERPRINT ----------------
    fingerprint = build_menu_fingerprint(
        name=name,
        section=section,
        currency=currency,
    )

    return NormalizedMenuItem(
        name=name,
        section=section,
        price_cents=price_cents,
        currency=currency,
        description=description,
        image_url=getattr(item, "image_url", None),  # 🔥 SAFE
        fingerprint=fingerprint,

        # passthrough
        provider=getattr(item, "provider", None),
        provider_item_id=getattr(item, "provider_item_id", None),
        source_url=getattr(item, "source_url", None),
        source_type=getattr(item, "source_type", None),
        is_available=getattr(item, "is_available", None),
        badges=getattr(item, "badges", []) or [],
    )


# ---------------------------------------------------------
# 🔥 BATCH NORMALIZATION (CRITICAL FIX)
# ---------------------------------------------------------

def normalize_menu_items(
    items: List[ExtractedMenuItem],
) -> List[NormalizedMenuItem]:

    out: List[NormalizedMenuItem] = []

    for item in items:
        try:
            normalized = normalize_menu_item(item)
            if normalized:
                out.append(normalized)
        except Exception:
            continue

    return out