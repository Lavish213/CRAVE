from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# -----------------------------------------------------
# ENTRYPOINT
# -----------------------------------------------------

def extract_menu_from_toast_payloads(
    payloads: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extracts menu items from Toast GraphQL / Apollo payloads.

    Returns normalized menu items:
    [
        {
            "name": str,
            "price": float,
            "description": str | None,
            "image": str | None,
            "category": str | None
        }
    ]
    """

    items: List[Dict[str, Any]] = []

    try:
        for payload in payloads:
            items.extend(_extract_from_payload(payload))

    except Exception as e:
        logger.error("toast_menu_extract_failed error=%s", e)

    logger.info("toast_menu_extract_complete items=%s", len(items))

    return items


# -----------------------------------------------------
# INTERNAL PARSERS
# -----------------------------------------------------

def _extract_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    # Apollo normalized cache style
    for key, value in payload.items():

        if not isinstance(value, dict):
            continue

        typename = value.get("__typename")

        # -------------------------------------------------
        # MENU GROUPS / SECTIONS
        # -------------------------------------------------
        if typename in ("MenuGroup", "MenuSection", "MenuCategory"):
            category_name = value.get("name")

            for item in _walk_items(value):
                parsed = _parse_item(item, category_name)
                if parsed:
                    results.append(parsed)

        # -------------------------------------------------
        # DIRECT MENU ITEM
        # -------------------------------------------------
        if typename in ("MenuItem", "MenuItemEntity"):
            parsed = _parse_item(value, None)
            if parsed:
                results.append(parsed)

    return results


def _walk_items(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Recursively find menu items inside nested structures
    """

    found: List[Dict[str, Any]] = []

    for key, value in node.items():

        if isinstance(value, list):
            for v in value:
                if isinstance(v, dict):
                    found.extend(_walk_items(v))

        elif isinstance(value, dict):
            typename = value.get("__typename")

            if typename in ("MenuItem", "MenuItemEntity"):
                found.append(value)
            else:
                found.extend(_walk_items(value))

    return found


def _parse_item(
    item: Dict[str, Any],
    category: Optional[str]
) -> Optional[Dict[str, Any]]:

    try:
        name = item.get("name")
        if not name:
            return None

        price = _extract_price(item)

        description = item.get("description")

        image = _extract_image(item)

        return {
            "name": name,
            "price": price,
            "description": description,
            "image": image,
            "category": category,
        }

    except Exception:
        return None


# -----------------------------------------------------
# HELPERS
# -----------------------------------------------------

def _extract_price(item: Dict[str, Any]) -> Optional[float]:
    """
    Handles multiple Toast price formats
    """

    price = item.get("price")

    if isinstance(price, (int, float)):
        return round(price / 100, 2) if price > 100 else float(price)

    pricing = item.get("pricing") or {}

    amount = pricing.get("price") or pricing.get("amount")

    if isinstance(amount, (int, float)):
        return round(amount / 100, 2)

    return None


def _extract_image(item: Dict[str, Any]) -> Optional[str]:
    """
    Extracts image from Toast formats
    """

    image = item.get("image") or {}

    if isinstance(image, dict):
        return image.get("displaySrc") or image.get("src")

    photos = item.get("photos")

    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            return first.get("displaySrc") or first.get("src")

    return None