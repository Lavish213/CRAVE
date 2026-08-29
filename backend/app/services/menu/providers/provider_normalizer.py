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
    seen: Set[tuple[str, Optional[int], Optional[str]]] = set()

    for item in items:

        try:

            name = _clean_name(item.name, provider)
            if not name:
                continue

            price_cents = _clean_price_to_cents(item.price_cents)

            section = _clean_section(item.section)

            description = _clean_text(item.description)

            fingerprint = build_menu_fingerprint(
                name=name,
                section=section,
                currency="USD",
            )

            dedupe_key = (fingerprint, price_cents, item.provider_item_id)

            if not fingerprint or dedupe_key in seen:
                continue

            seen.add(dedupe_key)

            normalized.append(
                ExtractedMenuItem(
                    name=name,
                    price_cents=price_cents,
                    section=section,
                    currency="USD",
                    description=description,
                    image_url=_clean_text(item.image_url),
                    provider=provider or item.provider,
                    provider_item_id=item.provider_item_id,
                    is_available=item.is_available,
                    badges=list(item.badges),
                    source_type=item.source_type,
                    source_url=item.source_url,
                    modifiers=list(item.modifiers),
                    raw=item.raw,
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
        # ExtractedMenuItem's active contract stores integer cents. Preserve
        # those values instead of interpreting 725 cents as $725.00.
        if isinstance(value, int) and not isinstance(value, bool):
            return value if 0 < value <= 100_000 else None

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
