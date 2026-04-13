from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.services.menu.contracts import ExtractedMenuItem
from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500
MAX_DEPTH = 25


# ---------------------------------------------------------
# GraphQL fallback queries
# ---------------------------------------------------------

GRAPHQL_QUERIES = [
"""
query MenuQuery {
  menu {
    sections {
      name
      items {
        name
        description
        price
      }
    }
  }
}
""",
"""
query Products {
  products {
    name
    description
    price
  }
}
""",
"""
query Catalog {
  catalog {
    categories {
      name
      products {
        name
        price
        description
      }
    }
  }
}
""",
"""
query MenuItems {
  menuItems {
    name
    description
    price
  }
}
""",
"""
query AllItems {
  items {
    name
    description
    price
  }
}
""",
]


# ---------------------------------------------------------
# Price sanitizer
# ---------------------------------------------------------

_PRICE_SANITIZER = re.compile(r"[^\d\.]")


def _safe_price(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        if isinstance(value, (int, float)):
            return str(value)

        value = _PRICE_SANITIZER.sub("", str(value))
        return value or None

    except Exception:
        return None


# ---------------------------------------------------------
# Field extraction
# ---------------------------------------------------------

def _extract_name(obj: Dict[str, Any]) -> Optional[str]:
    for key in ("name", "title", "itemName", "productName", "displayName", "label"):
        value = obj.get(key)
        if value:
            value = str(value).strip()
            if value:
                return value
    return None


def _extract_price(obj: Dict[str, Any]) -> Optional[str]:
    for key in ("price", "amount", "cost", "basePrice", "unitPrice", "salePrice"):
        if obj.get(key) is not None:
            return _safe_price(obj.get(key))

    offers = obj.get("offers")
    if isinstance(offers, dict) and offers.get("price") is not None:
        return _safe_price(offers.get("price"))

    return None


def _extract_section(obj: Dict[str, Any], current: Optional[str]) -> Optional[str]:
    for key in ("section", "category", "menuSection", "group", "collection", "categoryName", "groupName"):
        value = obj.get(key)
        if value:
            value = str(value).strip()
            if value:
                return value
    return current


def _extract_description(obj: Dict[str, Any]) -> Optional[str]:
    for key in ("description", "details", "desc", "summary", "longDescription"):
        value = obj.get(key)
        if value:
            value = str(value).strip()
            if value:
                return value
    return None


# ---------------------------------------------------------
# Item detection
# ---------------------------------------------------------

def _looks_like_menu_item(obj: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict):
        return False

    name = _extract_name(obj)
    price = _extract_price(obj)

    if name and price is not None:
        return True

    if name and _extract_description(obj):
        return True

    return False


# ---------------------------------------------------------
# Recursive scan (with cycle protection)
# ---------------------------------------------------------

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

    # Prevent infinite recursion
    if isinstance(data, dict):
        node_id = id(data)
        if node_id in seen_nodes:
            return items
        seen_nodes.add(node_id)

    # GraphQL edges/nodes pattern
    if isinstance(data, dict):
        if "edges" in data and isinstance(data["edges"], list):
            for edge in data["edges"]:
                if isinstance(edge, dict) and "node" in edge:
                    _scan(edge["node"], depth=depth + 1, current_section=current_section, items=items, seen_nodes=seen_nodes)

        if "nodes" in data and isinstance(data["nodes"], list):
            for node in data["nodes"]:
                _scan(node, depth=depth + 1, current_section=current_section, items=items, seen_nodes=seen_nodes)

    # List traversal
    if isinstance(data, list):
        for value in data:
            _scan(value, depth=depth + 1, current_section=current_section, items=items, seen_nodes=seen_nodes)
        return items

    if not isinstance(data, dict):
        return items

    next_section = current_section

    if "name" in data and any(k in data for k in ("items", "products", "children", "menuItems", "dishes")):
        name_value = data.get("name")
        if isinstance(name_value, str) and name_value.strip():
            next_section = name_value.strip()

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

    for value in data.values():
        if isinstance(value, (dict, list)):
            _scan(value, depth=depth + 1, current_section=next_section, items=items, seen_nodes=seen_nodes)

    return items


# ---------------------------------------------------------
# Dedupe
# ---------------------------------------------------------

def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    seen: Set[str] = set()
    unique: List[ExtractedMenuItem] = []

    for item in items:
        key = f"{(item.name or '').lower()}|{(item.price or '')}|{(item.section or '').lower()}"

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

        if len(unique) >= MAX_ITEMS:
            break

    return unique


# ---------------------------------------------------------
# GraphQL execution
# ---------------------------------------------------------

def _run_query(graphql_url: str, query: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    try:
        response = fetch(
            graphql_url,
            method="POST",
            headers=headers,
            json={"query": query},
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception:
        return None


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def extract_graphql_menu(
    graphql_url: str,
    referer: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not graphql_url:
        return []

    try:

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }

        if referer:
            headers["Referer"] = referer


        data = None

        # ---------------------------------------------------------
        # Try GET first
        # ---------------------------------------------------------

        try:
            response = fetch(graphql_url, headers=headers)

            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    data = None

        except Exception:
            pass

        # ---------------------------------------------------------
        # Fallback queries
        # ---------------------------------------------------------

        if not data:
            for query in GRAPHQL_QUERIES:
                data = _run_query(graphql_url, query, headers)
                if data:
                    break

        if not data:
            return []

        if isinstance(data, dict) and "data" in data:
            data = data["data"]

        items = _scan(data)
        items = _dedupe(items)

        if items:
            logger.info(
                "graphql_menu_extracted items=%s endpoint=%s",
                len(items),
                graphql_url,
            )

        return items

    except Exception as exc:
        logger.debug(
            "graphql_menu_extraction_failed endpoint=%s error=%s",
            graphql_url,
            exc,
        )
        return []