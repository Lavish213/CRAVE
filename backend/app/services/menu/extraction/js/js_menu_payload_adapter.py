from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Any, Set

from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500
MAX_DEPTH = 12


# ---------------------------------------------------------
# Key hints (EXPANDED)
# ---------------------------------------------------------

NAME_KEYS = {"name", "title", "label", "itemname", "productname"}
PRICE_KEYS = {"price", "amount", "displayprice", "unitprice", "baseprice", "cost"}
DESC_KEYS = {"description", "desc", "details"}
SECTION_KEYS = {"section", "category", "group", "menu", "menuname", "categoryname", "sectionname", "groupname"}
IMAGE_KEYS = {"image", "imageurl", "photo", "picture", "img"}


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _lower_keys(obj: Dict) -> Dict:
    return {str(k).lower(): v for k, v in obj.items()}


def _find_value(obj: Dict, keys: set) -> Optional[Any]:
    for k, v in obj.items():
        if k in keys:
            return v

        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if sub_k in keys:
                    return sub_v

    return None


def _normalize_price(value: Any) -> Optional[str]:

    if value is None:
        return None

    try:

        # nested dicts
        if isinstance(value, dict):
            for k in ("amount", "value", "price"):
                if k in value:
                    return _normalize_price(value[k])

        # numeric
        if isinstance(value, (int, float)):
            num = float(value)

            # 🔥 FIX: handle cents (e.g., 599 → 5.99)
            if num > 100:
                num = num / 100

            if num <= 0:
                return None

            return f"{num:.2f}"

        text = str(value)

        # extract number
        match = re.search(r"\d+(?:[.,]\d+)?", text)
        if not match:
            return None

        number = match.group(0).replace(",", ".")

        num = float(number)

        if num > 100:
            num = num / 100

        if num <= 0:
            return None

        return f"{num:.2f}"

    except Exception:
        return None


def _clean_text(value: Any) -> Optional[str]:

    if not value:
        return None

    try:
        text = str(value).strip()

        if len(text) < 2:
            return None

        if len(text) > 120:
            return None

        return text

    except Exception:
        return None


def _looks_like_menu_item(node: Dict) -> bool:

    keys = set(node.keys())

    if not keys & NAME_KEYS:
        return False

    if keys & {"modifier", "option", "choice", "size"}:
        return False

    return True


# ---------------------------------------------------------
# Object walker (SAFE DEPTH)
# ---------------------------------------------------------

def _walk(obj: Any, current_section: Optional[str] = None, depth: int = 0):

    if depth > MAX_DEPTH:
        return

    if isinstance(obj, dict):

        lowered = _lower_keys(obj)

        section = _find_value(lowered, SECTION_KEYS) or current_section

        yield lowered, section

        for value in lowered.values():
            yield from _walk(value, section, depth + 1)

    elif isinstance(obj, list):

        for value in obj:
            yield from _walk(value, current_section, depth + 1)


# ---------------------------------------------------------
# Item builder
# ---------------------------------------------------------

def _build_item(node: Dict, section: Optional[str]) -> Optional[ExtractedMenuItem]:

    name = _clean_text(_find_value(node, NAME_KEYS))

    if not name:
        return None

    price = _normalize_price(_find_value(node, PRICE_KEYS))

    description = _clean_text(_find_value(node, DESC_KEYS))

    image_val = _find_value(node, IMAGE_KEYS)
    image = str(image_val).strip() if image_val else None

    lower_name = name.lower()

    if lower_name in {"add", "add to cart", "select", "choose"}:
        return None

    try:
        return ExtractedMenuItem(
            name=name,
            price=price,
            description=description,
            section=_clean_text(section),
            image=image,
        )
    except Exception:
        return None


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def convert_payload_to_menu_items(
    payload: Any,
) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    if not payload:
        return items

    seen: Set[str] = set()

    try:

        for node, section in _walk(payload):

            if not isinstance(node, dict):
                continue

            if not _looks_like_menu_item(node):
                continue

            item = _build_item(node, section)

            if not item:
                continue

            key = (
                f"{item.name.lower()}|"
                f"{item.price or ''}|"
                f"{item.section or ''}"
            )

            if key in seen:
                continue

            seen.add(key)
            items.append(item)

            if len(items) >= MAX_ITEMS:
                break

    except Exception as exc:
        logger.debug("js_menu_payload_adapter_failed error=%s", exc)

    logger.info("js_payload_converted items=%s", len(items))

    return items