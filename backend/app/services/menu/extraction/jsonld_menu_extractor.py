from __future__ import annotations

import json
import logging
from typing import Iterable, List, Optional, Set

from bs4 import BeautifulSoup

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.heuristics import clean_text


logger = logging.getLogger(__name__)


MAX_ITEMS = 500


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _flatten_json_ld(data) -> Iterable[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _flatten_json_ld(item)

    elif isinstance(data, dict):
        yield data

        if "@graph" in data:
            yield from _flatten_json_ld(data["@graph"])


def _extract_price(obj: dict) -> Optional[str]:
    offers = obj.get("offers")

    if isinstance(offers, dict):
        price = offers.get("price")
        if price is not None:
            return str(price)

    if isinstance(offers, list):
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            price = offer.get("price")
            if price is not None:
                return str(price)

    return None


def _normalize_price(price: Optional[str]) -> Optional[str]:
    if not price:
        return None
    return str(price).replace("$", "").strip()


def _clean_name(name: str) -> Optional[str]:
    text = clean_text(name)
    if not text or len(text) < 2:
        return None
    return text.strip()


def _build_key(name: str, price: Optional[str]) -> str:
    return f"{name.lower()}|{price or ''}"


# ---------------------------------------------------------
# 🔥 NEW: Handle Menu → Section → Item structures
# ---------------------------------------------------------

def _extract_from_menu_structure(obj: dict) -> List[dict]:
    items = []

    has_menu = obj.get("hasMenu")
    has_menu_section = obj.get("hasMenuSection")
    has_menu_item = obj.get("hasMenuItem")

    for field in (has_menu, has_menu_section, has_menu_item):
        if isinstance(field, dict):
            items.append(field)
        elif isinstance(field, list):
            items.extend(field)

    return items


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def extract_jsonld_menu(
    html: str,
    source_url: str | None = None,
) -> List[ExtractedMenuItem]:

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    seen: Set[str] = set()
    items: List[ExtractedMenuItem] = []

    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:

        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        for obj in _flatten_json_ld(data):

            if not isinstance(obj, dict):
                continue

            obj_type = obj.get("@type")

            if isinstance(obj_type, list):
                obj_type = obj_type[0] if obj_type else None

            # ---------------------------------------------------------
            # 🔥 DIRECT ITEMS (original logic)
            # ---------------------------------------------------------

            if obj_type in {"MenuItem", "Product"}:

                name = obj.get("name")
                if not name:
                    continue

                clean_name = _clean_name(name)
                if not clean_name:
                    continue

                price = _normalize_price(_extract_price(obj))

                key = _build_key(clean_name, price)

                if key in seen:
                    continue

                seen.add(key)

                items.append(
                    ExtractedMenuItem(
                        name=clean_name,
                        price=price,
                        section=None,
                        currency="USD",
                        description=clean_text(obj.get("description") or ""),
                        source_url=source_url,
                        source_type="jsonld",
                    )
                )

            # ---------------------------------------------------------
            # 🔥 NEW: Nested menu extraction
            # ---------------------------------------------------------

            nested = _extract_from_menu_structure(obj)

            for sub in nested:

                if not isinstance(sub, dict):
                    continue

                name = sub.get("name")
                if not name:
                    continue

                clean_name = _clean_name(name)
                if not clean_name:
                    continue

                price = _normalize_price(_extract_price(sub))

                key = _build_key(clean_name, price)

                if key in seen:
                    continue

                seen.add(key)

                items.append(
                    ExtractedMenuItem(
                        name=clean_name,
                        price=price,
                        section=None,
                        currency="USD",
                        description=clean_text(sub.get("description") or ""),
                        source_url=source_url,
                        source_type="jsonld",
                    )
                )

                if len(items) >= MAX_ITEMS:
                    return items

            if len(items) >= MAX_ITEMS:
                return items

    logger.debug(
        "jsonld_menu_extracted count=%s url=%s",
        len(items),
        source_url,
    )

    return items