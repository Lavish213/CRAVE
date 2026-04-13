from __future__ import annotations

import logging
import re
from typing import List, Optional, Set

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.normalization.fingerprint import build_menu_fingerprint


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500


def normalize_items(
    items: List[ExtractedMenuItem],
    *,
    provider: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not items:
        return []

    normalized: List[ExtractedMenuItem] = []
    seen: Set[str] = set()

    for item in items:

        try:

            name = _clean_name(item.name, provider)
            if not name:
                continue

            price_cents = _clean_price_to_cents(item.price)

            section = _clean_section(item.section)

            description = _clean_text(item.description)

            fingerprint = build_menu_fingerprint(
                name=name,
                section=section,
                currency="USD",
            )

            if not fingerprint or fingerprint in seen:
                continue

            seen.add(fingerprint)

            normalized.append(
                ExtractedMenuItem(
                    name=name,
                    price=price_cents,  # 🔥 now INT (cents)
                    section=section,
                    currency="USD",
                    description=description,
                )
            )

            if len(normalized) >= MAX_ITEMS:
                break

        except Exception as exc:
            logger.debug("normalize_item_failed error=%s", exc)
            continue

    return normalized


# =========================================================
# CLEANING
# =========================================================

def _clean_text(value) -> Optional[str]:

    if not value:
        return None

    try:
        text = str(value)

        # remove weird unicode / emojis
        text = text.encode("ascii", "ignore").decode()

        text = text.strip()

        if not text:
            return None

        # normalize whitespace
        text = " ".join(text.split())

        return text

    except Exception:
        return None


def _clean_name(value, provider: Optional[str]) -> Optional[str]:

    text = _clean_text(value)
    if not text:
        return None

    # remove ALL CAPS junk
    if text.isupper():
        text = text.title()

    # remove trailing junk (common in scraped menus)
    text = re.sub(r"\(.*?\)$", "", text).strip()

    # provider-specific cleanup
    if provider == "grubhub":
        text = text.replace("NEW!", "").strip()

    return text


def _clean_section(value) -> str:

    text = _clean_text(value)

    if not text:
        return "Other"

    text = text.title()

    # normalize common garbage sections
    if text.lower() in {"menu", "food", "items"}:
        return "Other"

    return text


def _clean_price_to_cents(value) -> Optional[int]:

    if value is None:
        return None

    try:
        text = str(value)

        # remove currency + junk
        cleaned = "".join(c for c in text if c.isdigit() or c == ".")

        if not cleaned:
            return None

        # convert to float → cents
        dollars = float(cleaned)

        if dollars <= 0 or dollars > 1000:  # sanity check
            return None

        return int(round(dollars * 100))

    except Exception:
        return None