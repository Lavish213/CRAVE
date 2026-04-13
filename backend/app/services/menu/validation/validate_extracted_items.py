from __future__ import annotations

from typing import List

from app.services.menu.contracts import ExtractedMenuItem


def validate_extracted_items(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    valid: List[ExtractedMenuItem] = []

    for item in items:

        # ---------------- NAME ----------------
        name = _clean_str(item.name)
        if not name:
            continue
        item.name = name

        # ---------------- SECTION ----------------
        section = _clean_str(item.section) or "uncategorized"
        item.section = section

        # ---------------- DESCRIPTION ----------------
        item.description = _clean_str(item.description)

        # ---------------- PRICE ----------------
        price_cents = item.price_cents

        if price_cents is not None:
            try:
                price_cents = int(price_cents)
                if price_cents < 0:
                    price_cents = None
            except Exception:
                price_cents = None

        item.price_cents = price_cents

        # ---------------- MIN / MAX PRICE ----------------
        min_price = _safe_int(item.min_price_cents)
        max_price = _safe_int(item.max_price_cents)

        if min_price is not None and min_price < 0:
            min_price = None

        if max_price is not None and max_price < 0:
            max_price = None

        item.min_price_cents = min_price
        item.max_price_cents = max_price

        # ---------------- CURRENCY ----------------
        currency = _clean_str(item.currency)
        item.currency = currency.upper() if currency else "USD"

        # ---------------- PROVIDER ----------------
        item.provider = _clean_str(item.provider) or "unknown"

        # ---------------- BADGES ----------------
        if not isinstance(item.badges, list):
            item.badges = []

        item.badges = [
            str(b).strip()
            for b in item.badges
            if b and str(b).strip()
        ]

        # ---------------- MODIFIERS ----------------
        if not isinstance(item.modifiers, list):
            item.modifiers = []

        item.modifiers = [
            m for m in item.modifiers if isinstance(m, dict)
        ]

        # ---------------- FINAL GUARD ----------------
        if not item.name:
            continue

        valid.append(item)

    return valid


# =========================================================
# HELPERS
# =========================================================

def _clean_str(value) -> str | None:
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None