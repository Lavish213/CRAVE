from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.services.menu.contracts import ExtractedMenuItem
from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500
MAX_DEPTH = 25
MAX_UNWRAP_DEPTH = 5

REQUEST_TIMEOUT = 8.0


_PRICE_SANITIZER = re.compile(r"[^\d\.]")


# =========================================================
# CLEAN HELPERS
# =========================================================

def _safe_price(value: Any) -> Optional[str]:
    try:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return str(value)

        value = str(value)
        value = _PRICE_SANITIZER.sub("", value)

        return value or None

    except Exception:
        return None


def _extract_name(obj: Dict[str, Any]) -> Optional[str]:
    for key in (
        "name", "title", "itemName", "productName",
        "displayName", "label",
    ):
        value = obj.get(key)
        if value:
            v = str(value).strip()
            if v:
                return v
    return None


def _extract_price(obj: Dict[str, Any]) -> Optional[str]:
    for key in (
        "price", "amount", "cost",
        "basePrice", "unitPrice", "salePrice",
    ):
        if obj.get(key) is not None:
            return _safe_price(obj.get(key))

    offers = obj.get("offers")

    if isinstance(offers, dict):
        return _safe_price(offers.get("price"))

    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                return _safe_price(offer.get("price"))

    return None


def _extract_description(obj: Dict[str, Any]) -> Optional[str]:
    for key in ("description", "details", "desc", "summary", "longDescription"):
        value = obj.get(key)
        if value:
            v = str(value).strip()
            if v:
                return v
    return None


def _extract_section(obj: Dict[str, Any], current: Optional[str]) -> Optional[str]:
    for key in (
        "section", "category", "menuSection",
        "group", "collection", "categoryName", "groupName",
    ):
        value = obj.get(key)
        if value:
            v = str(value).strip()
            if v:
                return v
    return current


# =========================================================
# ITEM DETECTION (STRONGER FILTER)
# =========================================================

def _looks_like_menu_item(obj: Dict[str, Any]) -> bool:

    name = _extract_name(obj)
    price = _extract_price(obj)

    if not name:
        return False

    # 🔥 Strong filter
    if price:
        return True

    # allow description-based menus
    if _extract_description(obj):
        return True

    # reject modifiers/options
    if any(k in obj for k in ("modifier", "option", "choice", "addon")):
        return False

    return False


# =========================================================
# SCANNER
# =========================================================

def _scan(
    data: Any,
    *,
    depth: int = 0,
    current_section: Optional[str] = None,
    items: Optional[List[ExtractedMenuItem]] = None,
    seen_nodes: Optional[Set[int]] = None,
) -> List[ExtractedMenuItem]:

    if items is None:
        items = []

    if seen_nodes is None:
        seen_nodes = set()

    if depth > MAX_DEPTH or len(items) >= MAX_ITEMS:
        return items

    if isinstance(data, list):
        for v in data:
            _scan(v, depth=depth + 1, current_section=current_section, items=items, seen_nodes=seen_nodes)
        return items

    if not isinstance(data, dict):
        return items

    node_id = id(data)
    if node_id in seen_nodes:
        return items
    seen_nodes.add(node_id)

    next_section = current_section

    if "name" in data and any(k in data for k in ("items", "products", "children", "entries")):
        next_section = str(data.get("name")).strip()

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
                )
            )

    for v in data.values():
        if isinstance(v, (dict, list)):
            _scan(v, depth=depth + 1, current_section=next_section, items=items, seen_nodes=seen_nodes)

    return items


# =========================================================
# UNWRAP
# =========================================================

def _unwrap_response(data: Any) -> Any:
    for _ in range(MAX_UNWRAP_DEPTH):
        if not isinstance(data, dict):
            break

        for key in ("data", "payload", "result", "menu", "menus", "response", "results"):
            if key in data:
                data = data[key]
                break
        else:
            break

    return data


# =========================================================
# MAIN ENTRY
# =========================================================

def extract_api_menu(api_url: str, referer: Optional[str] = None) -> List[ExtractedMenuItem]:

    try:

        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
        }

        if referer:
            headers["Referer"] = referer

        response = fetch(
            api_url,
            method="GET",
            mode="api",   # 🔥 CRITICAL FIX
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            logger.debug("api_bad_status url=%s status=%s", api_url, response.status_code)
            return []

        try:
            data = response.json()
        except Exception:
            data = json.loads(response.text)

        if not data:
            return []

        data = _unwrap_response(data)

        items = _scan(data)

        if not items:
            return []

        # dedupe
        seen = set()
        final = []

        for item in items:
            key = f"{item.name}|{item.price}|{item.section}"

            if key in seen:
                continue

            seen.add(key)
            final.append(item)

            if len(final) >= MAX_ITEMS:
                break

        logger.info(
            "api_menu_extracted items=%s endpoint=%s",
            len(final),
            api_url,
        )

        return final

    except Exception as exc:
        logger.debug(
            "api_menu_extraction_failed endpoint=%s error=%s",
            api_url,
            exc,
        )
        return []