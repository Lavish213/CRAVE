from __future__ import annotations

from typing import List

from app.services.menu.contracts import NormalizedMenuItem
from app.services.menu.normalization.fingerprint import build_menu_fingerprint


def validate_normalized_items(items: List[NormalizedMenuItem]) -> List[NormalizedMenuItem]:
    valid: List[NormalizedMenuItem] = []

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

        # ---------------- CURRENCY ----------------
        currency = _clean_str(item.currency)
        currency = currency.upper() if currency else "USD"
        item.currency = currency

        # ---------------- FINGERPRINT (🔥 HARD RESET) ----------------
        # ALWAYS rebuild → guarantees consistency across system
        item.fingerprint = build_menu_fingerprint(
            name=item.name,
            section=item.section,
            currency=item.currency,
        )

        # ---------------- FINAL GUARD ----------------
        if not item.fingerprint:
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