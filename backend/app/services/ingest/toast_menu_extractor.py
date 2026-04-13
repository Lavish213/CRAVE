from __future__ import annotations

import logging
from typing import Dict, List, Any, Set, Optional

logger = logging.getLogger(__name__)


# -----------------------------------------------------
# ENTRYPOINT (FINAL PRODUCTION)
# -----------------------------------------------------

def extract_menu_from_toast_payloads(
    payloads: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    items: List[Dict[str, Any]] = []

    try:
        lookup = _build_lookup(payloads)

        seen: Set[str] = set()
        primary_count = 0
        fallback_count = 0

        # -----------------------------
        # PRIMARY (Apollo)
        # -----------------------------
        for payload in payloads:
            extracted = _extract_from_payload(payload, lookup)

            for item in extracted:
                key = _dedupe_key(item)

                if key in seen:
                    continue

                seen.add(key)
                items.append(item)
                primary_count += 1

        # -----------------------------
        # FALLBACK (GUARANTEED)
        # -----------------------------
        if not items:
            logger.warning("apollo_extract_empty_fallback_scan")

            for payload in payloads:
                for raw in _scan_all(payload):

                    parsed = _parse_item(raw, None)
                    if not parsed:
                        continue

                    key = _dedupe_key(parsed)

                    if key in seen:
                        continue

                    seen.add(key)
                    items.append(parsed)
                    fallback_count += 1

        logger.info(
            "toast_extract_summary primary=%s fallback=%s total=%s",
            primary_count,
            fallback_count,
            len(items),
        )

    except Exception:
        logger.exception("toast_menu_extract_failed")

    logger.info("toast_menu_extract_complete items=%s", len(items))

    return items


# -----------------------------------------------------
# LOOKUP BUILDER (FIXED)
# -----------------------------------------------------

def _build_lookup(payloads: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}

    def walk(node: Any):
        if isinstance(node, dict):

            typename = node.get("__typename")
            entity_id = node.get("id")

            if typename and entity_id:
                key = f"{typename}:{entity_id}"
                lookup[key] = node

            for v in node.values():
                walk(v)

        elif isinstance(node, list):
            for item in node:
                walk(item)

    for payload in payloads:
        walk(payload)

    return lookup


# -----------------------------------------------------
# EXTRACTION
# -----------------------------------------------------

def _extract_from_payload(payload, lookup):

    results: List[Dict[str, Any]] = []

    for value in payload.values():

        if not isinstance(value, dict):
            continue

        typename = value.get("__typename")

        if typename in ("MenuGroup", "MenuSection", "MenuCategory"):
            category = value.get("name")

            for item in _walk_items(value, lookup):
                parsed = _parse_item(item, category)
                if parsed:
                    results.append(parsed)

        if typename in ("MenuItem", "MenuItemEntity"):
            parsed = _parse_item(value, None)
            if parsed:
                results.append(parsed)

    return results


# -----------------------------------------------------
# WALK + RESOLVE
# -----------------------------------------------------

def _walk_items(node, lookup):

    found = []

    if isinstance(node, dict):

        if "__ref" in node:
            ref = lookup.get(node["__ref"])
            if ref:
                return _walk_items(ref, lookup)
            return []

        typename = node.get("__typename")

        if typename in ("MenuItem", "MenuItemEntity"):
            return [node]

        for v in node.values():
            found.extend(_walk_items(v, lookup))

    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_items(item, lookup))

    return found


# -----------------------------------------------------
# FALLBACK SCAN
# -----------------------------------------------------

def _scan_all(node):

    found = []

    if isinstance(node, dict):

        if node.get("__typename") in ("MenuItem", "MenuItemEntity"):
            found.append(node)

        for v in node.values():
            found.extend(_scan_all(v))

    elif isinstance(node, list):
        for item in node:
            found.extend(_scan_all(item))

    return found


# -----------------------------------------------------
# PARSER (FINAL)
# -----------------------------------------------------

def _parse_item(item, category):

    try:
        name = item.get("name")
        if not name:
            return None

        if not category:
            category = (
                item.get("categoryName")
                or item.get("menuGroupName")
            )

        price = _extract_price(item)

        return {
            "name": name.strip(),
            "price": price,
            "description": (item.get("description") or "").strip(),
            "image": _extract_image(item),
            "category": category,
        }

    except Exception:
        return None


# -----------------------------------------------------
# PRICE RESOLVER (FULL)
# -----------------------------------------------------

def _extract_price(item) -> Optional[float]:

    # -----------------------------
    # direct
    # -----------------------------
    price = item.get("price")
    if isinstance(price, (int, float)):
        return _normalize(price)

    # -----------------------------
    # pricing object
    # -----------------------------
    pricing = item.get("pricing") or {}
    amount = pricing.get("price") or pricing.get("amount")

    if isinstance(amount, (int, float)):
        return _normalize(amount)

    # -----------------------------
    # prices array
    # -----------------------------
    prices = item.get("prices")
    if isinstance(prices, list):
        for p in prices:
            if isinstance(p, (int, float)):
                return _normalize(p)

    # -----------------------------
    # variants
    # -----------------------------
    variants = item.get("variants") or []
    if isinstance(variants, list):
        for v in variants:
            pricing = v.get("pricing") or {}
            amount = pricing.get("price") or pricing.get("amount")

            if isinstance(amount, (int, float)):
                return _normalize(amount)

    # -----------------------------
    # price levels
    # -----------------------------
    price_levels = item.get("priceLevels") or []
    if isinstance(price_levels, list):
        for p in price_levels:
            amount = p.get("price")
            if isinstance(amount, (int, float)):
                return _normalize(amount)

    # -----------------------------
    # price range (fallback)
    # -----------------------------
    price_range = item.get("priceRange") or {}
    if isinstance(price_range, dict):
        amount = price_range.get("min")
        if isinstance(amount, (int, float)):
            return _normalize(amount)

    return None


def _normalize(v):
    return round(v / 100, 2) if v > 100 else float(v)


# -----------------------------------------------------
# IMAGE
# -----------------------------------------------------

def _extract_image(item):

    image = item.get("image") or {}

    if isinstance(image, dict):
        return image.get("displaySrc") or image.get("src")

    photos = item.get("photos")

    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            return first.get("displaySrc") or first.get("src")

    return None


# -----------------------------------------------------
# DEDUPE
# -----------------------------------------------------

def _dedupe_key(item):
    return f"{item.get('name')}|{item.get('price')}|{item.get('category')}"