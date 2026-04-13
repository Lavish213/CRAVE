from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_ITEMS = 1200


# ---------------------------------------------------------
# Square hydration patterns
# ---------------------------------------------------------

SQUARE_DATA_PATTERNS = [

    re.compile(
        r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});",
        re.DOTALL,
    ),

    re.compile(
        r"window\.Square\s*=\s*(\{.*?\});",
        re.DOTALL,
    ),

]


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _safe_json(raw: str) -> Optional[Any]:

    try:
        return json.loads(raw)
    except Exception:
        return None


def _safe_price(value: Any) -> Optional[str]:

    if value is None:
        return None

    try:

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


# ---------------------------------------------------------
# Recursive scanner
# ---------------------------------------------------------

def _scan(data: Any, items: List[ExtractedMenuItem]):

    if len(items) >= MAX_ITEMS:
        return

    if isinstance(data, list):

        for obj in data:
            _scan(obj, items)

        return

    if not isinstance(data, dict):
        return

    name = data.get("name")

    price = (
        data.get("price")
        or data.get("priceMoney")
        or data.get("amount")
    )

    if isinstance(price, dict):
        price = price.get("amount")

    if name and price is not None:

        items.append(
            ExtractedMenuItem(
                name=str(name).strip(),
                price=_safe_price(price),
                section=data.get("category")
                or data.get("section")
                or data.get("group"),
                currency="USD",
            )
        )

    for value in data.values():

        if isinstance(value, (dict, list)):
            _scan(value, items)


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
# Hydration extractor
# ---------------------------------------------------------

def _extract_from_hydration(html: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for pattern in SQUARE_DATA_PATTERNS:

        matches = pattern.findall(html)

        if not matches:
            continue

        for raw in matches:

            data = _safe_json(raw)

            if not data:
                continue

            _scan(data, items)

    return items


# ---------------------------------------------------------
# Public extractor
# ---------------------------------------------------------

def extract_square_menu(
    html: Optional[str] = None,
    url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not html:
        return []

    try:

        items = _extract_from_hydration(html)

        items = _dedupe(items)

        if items:

            logger.info(
                "square_menu_extracted items=%s url=%s",
                len(items),
                url,
            )

        return items

    except Exception as exc:

        logger.debug(
            "square_menu_parse_failed url=%s error=%s",
            url,
            exc,
        )

        return []