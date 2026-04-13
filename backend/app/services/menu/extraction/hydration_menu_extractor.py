from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500
MAX_RECURSION_DEPTH = 25
MAX_JSON_BLOB = 6_000_000


# ---------------------------------------------------------
# Hydration markers
# ---------------------------------------------------------

HYDRATION_MARKERS = [

    "__INITIAL_STATE__",
    "__NEXT_DATA__",
    "__APOLLO_STATE__",
    "__NUXT__",
    "__PRELOADED_STATE__",
    "__REDUX_STATE__",
    "APP_STATE",
    "__DATA__",
]


# ---------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------

def _extract_balanced_json(html: str, start_index: int) -> Optional[str]:

    depth = 0
    start = None

    for i in range(start_index, len(html)):

        char = html[i]

        if char == "{":

            if start is None:
                start = i

            depth += 1

        elif char == "}":

            depth -= 1

            if depth == 0 and start is not None:

                blob = html[start : i + 1]

                if len(blob) > MAX_JSON_BLOB:
                    return None

                return blob

    return None


def _find_hydration_blobs(html: str) -> List[str]:

    blobs: List[str] = []

    for marker in HYDRATION_MARKERS:

        pos = html.find(marker)

        if pos == -1:
            continue

        start = html.find("{", pos)

        if start == -1:
            continue

        blob = _extract_balanced_json(html, start)

        if blob:
            blobs.append(blob)

    return blobs


# ---------------------------------------------------------
# Safe JSON parsing
# ---------------------------------------------------------

def _safe_load_json(raw: str) -> Optional[Any]:

    if not raw:
        return None

    try:

        raw = raw.replace("\n", " ")
        raw = re.sub(r",\s*}", "}", raw)
        raw = re.sub(r",\s*]", "]", raw)

        return json.loads(raw)

    except Exception:
        return None


# ---------------------------------------------------------
# Price normalization
# ---------------------------------------------------------

def _normalize_price(value: Any) -> Optional[str]:

    if value is None:
        return None

    try:

        if isinstance(value, str):

            value = value.replace("$", "").strip()

            return value

        if isinstance(value, (int, float)):

            if value > 100:
                value = value / 100

            return str(round(value, 2))

    except Exception:
        pass

    return None


# ---------------------------------------------------------
# Menu heuristics
# ---------------------------------------------------------

def _looks_like_menu_item(obj: Dict[str, Any]) -> bool:

    name = obj.get("name") or obj.get("title") or obj.get("productName")

    price = (
        obj.get("price")
        or obj.get("basePrice")
        or obj.get("amount")
        or obj.get("cost")
    )

    if name and price is not None:
        return True

    if name and any(
        key in obj
        for key in (
            "description",
            "menuItem",
            "menuSection",
            "product",
            "category",
            "collection",
        )
    ):
        return True

    return False


# ---------------------------------------------------------
# Field extractors
# ---------------------------------------------------------

def _extract_name(obj: Dict[str, Any]) -> Optional[str]:

    value = (
        obj.get("name")
        or obj.get("title")
        or obj.get("productName")
        or obj.get("label")
    )

    if not value:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def _extract_price(obj: Dict[str, Any]) -> Optional[str]:

    for key in ("price", "basePrice", "amount", "cost"):

        if key in obj and obj[key] is not None:
            return _normalize_price(obj[key])

    offers = obj.get("offers")

    if isinstance(offers, dict):

        price = offers.get("price")

        if price is not None:
            return _normalize_price(price)

    if isinstance(offers, list):

        for offer in offers:

            if isinstance(offer, dict):

                price = offer.get("price")

                if price is not None:
                    return _normalize_price(price)

    return None


def _extract_section(obj: Dict[str, Any], current_section: Optional[str]) -> Optional[str]:

    for key in ("section", "category", "menuSection", "group", "collection"):

        value = obj.get(key)

        if value:

            if isinstance(value, dict):
                return str(value.get("name"))

            return str(value)

    return current_section


def _extract_description(obj: Dict[str, Any]) -> Optional[str]:

    desc = obj.get("description")

    if not desc:
        return None

    desc = str(desc).strip()

    if not desc:
        return None

    return desc


# ---------------------------------------------------------
# Recursive scanner
# ---------------------------------------------------------

def _scan(
    data: Any,
    *,
    depth: int = 0,
    current_section: Optional[str] = None,
    items: Optional[List[ExtractedMenuItem]] = None,
) -> List[ExtractedMenuItem]:

    if items is None:
        items = []

    if depth > MAX_RECURSION_DEPTH:
        return items

    if len(items) >= MAX_ITEMS:
        return items

    if isinstance(data, list):

        for value in data:

            _scan(
                value,
                depth=depth + 1,
                current_section=current_section,
                items=items,
            )

        return items

    if not isinstance(data, dict):
        return items

    next_section = current_section

    if "name" in data and any(k in data for k in ("items", "products", "children", "entries")):

        name_val = data.get("name")

        if isinstance(name_val, str) and name_val.strip():

            next_section = name_val.strip()

    if _looks_like_menu_item(data):

        name = _extract_name(data)

        if name:

            items.append(

                ExtractedMenuItem(

                    name=name,
                    price=_extract_price(data),
                    section=_extract_section(data, next_section),
                    currency="USD",
                    description=_extract_description(data),
                    source_type="hydration",
                    confidence=0.75,
                )
            )

    for value in data.values():

        if isinstance(value, (dict, list)):

            _scan(
                value,
                depth=depth + 1,
                current_section=next_section,
                items=items,
            )

    return items


# ---------------------------------------------------------
# Dedupe
# ---------------------------------------------------------

def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:

    seen = set()
    unique: List[ExtractedMenuItem] = []

    for item in items:

        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{(item.price or '').strip()}|"
            f"{(item.section or '').strip().lower()}"
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

        if len(unique) >= MAX_ITEMS:
            break

    return unique


# ---------------------------------------------------------
# Main extractor
# ---------------------------------------------------------

def extract_hydration_menu(
    html: str,
    url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not html:
        return []

    blobs = _find_hydration_blobs(html)

    if not blobs:
        return []

    extracted_items: List[ExtractedMenuItem] = []

    for raw in blobs:

        data = _safe_load_json(raw)

        if not data:
            continue

        items = _scan(data)

        if items:

            extracted_items.extend(items)

    extracted_items = _dedupe(extracted_items)

    if extracted_items:

        logger.info(
            "hydration_menu_extracted items=%s url=%s",
            len(extracted_items),
            url,
        )

    return extracted_items