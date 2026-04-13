from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)

MAX_ITEMS = 1200
MAX_RECURSION_DEPTH = 20


# ---------------------------------------------------------
# Clover menu payload patterns
# ---------------------------------------------------------

CLOVER_PATTERNS = [

    re.compile(
        r'"categories"\s*:\s*(\[[\s\S]*?\])',
        re.DOTALL | re.IGNORECASE
    ),

    re.compile(
        r'"menu"\s*:\s*(\{[\s\S]*?\})',
        re.DOTALL | re.IGNORECASE
    ),

    re.compile(
        r'window\.__PRELOADED_STATE__\s*=\s*(\{[\s\S]*?\});',
        re.DOTALL
    ),

    re.compile(
        r'window\.APP_STATE\s*=\s*(\{[\s\S]*?\});',
        re.DOTALL
    ),

    re.compile(
        r'window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\});',
        re.DOTALL
    ),
]


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _safe_json_load(raw: str) -> Optional[Any]:

    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


def _safe_price(value: Any) -> Optional[str]:

    if value is None:
        return None

    try:

        if isinstance(value, dict):

            value = (
                value.get("amount")
                or value.get("value")
                or value.get("price")
            )

        if isinstance(value, (int, float)):

            if value > 100:
                return str(round(value / 100, 2))

            return str(value)

        if isinstance(value, str):

            value = value.replace("$", "").strip()

            return value

    except Exception:
        pass

    return None


def _normalize_name(value: Any) -> Optional[str]:

    if value is None:
        return None

    name = str(value).strip()

    if not name:
        return None

    return name


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
# Payload discovery
# ---------------------------------------------------------

def _find_menu_payload(html: Optional[str]) -> Optional[Any]:

    if not html:
        return None

    for pattern in CLOVER_PATTERNS:

        match = pattern.search(html)

        if not match:
            continue

        raw = match.group(1) if match.groups() else match.group(0)

        data = _safe_json_load(raw)

        if data:
            return data

    return None


# ---------------------------------------------------------
# Recursive menu scanner
# ---------------------------------------------------------

def _scan(
    data: Any,
    *,
    items: List[ExtractedMenuItem],
    current_section: Optional[str] = None,
    depth: int = 0,
) -> None:

    if depth > MAX_RECURSION_DEPTH:
        return

    if len(items) >= MAX_ITEMS:
        return

    if isinstance(data, list):

        for value in data:
            _scan(value, items=items, current_section=current_section, depth=depth + 1)

        return

    if not isinstance(data, dict):
        return

    section = current_section

    # detect category sections
    if "name" in data and isinstance(data.get("items"), list):
        section = str(data["name"])

    # detect menu item nodes
    if "name" in data and (
        "price" in data
        or "amount" in data
        or "priceMoney" in data
        or "price_money" in data
    ):

        name = _normalize_name(data.get("name"))

        if name:

            price = (
                data.get("price")
                or data.get("amount")
                or data.get("priceMoney")
                or data.get("price_money")
            )

            description = data.get("description")

            image = (
                data.get("image")
                or data.get("imageUrl")
                or data.get("image_url")
            )

            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=_safe_price(price),
                    section=section,
                    currency="USD",
                    description=description,
                    image_url=image,
                    provider="clover",
                    source_type="provider",
                )
            )

    # recursive traversal
    for value in data.values():

        if isinstance(value, (list, dict)):

            _scan(
                value,
                items=items,
                current_section=section,
                depth=depth + 1,
            )


# ---------------------------------------------------------
# Public extractor
# ---------------------------------------------------------

def extract_clover_menu(
    html: Optional[str] = None,
    url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    try:

        payload = _find_menu_payload(html)

        if not payload:

            logger.debug(
                "clover_payload_not_found url=%s",
                url,
            )

            return []

        items: List[ExtractedMenuItem] = []

        _scan(payload, items=items)

        items = _dedupe(items)

        if items:

            logger.info(
                "clover_menu_extracted url=%s items=%s",
                url,
                len(items),
            )

        return items

    except Exception as exc:

        logger.debug(
            "clover_menu_parse_failed url=%s error=%s",
            url,
            exc,
        )

        return []