from __future__ import annotations

import json
import logging
from typing import Iterable, List, Optional, Set

from bs4 import BeautifulSoup

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.heuristics import clean_text
from app.services.menu.extraction.price_normalizer import coerce_price_cents


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

def _walk_menu_items(
    value,
    *,
    section: Optional[str] = None,
) -> Iterable[tuple[dict, Optional[str]]]:
    """Yield leaf MenuItem nodes from arbitrarily nested schema.org menus."""
    if isinstance(value, list):
        for entry in value:
            yield from _walk_menu_items(entry, section=section)
        return

    if not isinstance(value, dict):
        return

    obj_type = value.get("@type")
    if isinstance(obj_type, list):
        obj_type = obj_type[0] if obj_type else None

    current_section = section
    if obj_type == "MenuSection":
        current_section = _clean_name(value.get("name") or "") or section

    if obj_type == "MenuItem":
        yield value, current_section
        return

    for field in ("hasMenu", "hasMenuSection", "hasMenuItem"):
        nested = value.get(field)
        if nested is not None:
            yield from _walk_menu_items(nested, section=current_section)


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
                        price_cents=coerce_price_cents(price),
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

            for sub, section in _walk_menu_items(obj):
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
                        price_cents=coerce_price_cents(price),
                        section=section,
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
