from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500
MAX_RECURSION_DEPTH = 30


# ---------------------------------------------------------
# Generic field candidates
# ---------------------------------------------------------

NAME_KEYS = (
    "name",
    "title",
    "label",
    "displayName",
    "display_name",
    "productName",
    "product_name",
    "itemName",
    "item_name",
)

DESCRIPTION_KEYS = (
    "description",
    "desc",
    "details",
    "summary",
    "subtitle",
    "itemDescription",
    "item_description",
)

SECTION_KEYS = (
    "section",
    "sectionName",
    "section_name",
    "category",
    "categoryName",
    "category_name",
    "menuSection",
    "menu_section",
    "group",
    "groupName",
    "group_name",
    "collection",
    "collectionName",
    "collection_name",
)

IMAGE_KEYS = (
    "image",
    "imageUrl",
    "imageURL",
    "image_url",
    "photo",
    "photoUrl",
    "photo_url",
    "thumbnail",
    "thumbnailUrl",
    "thumbnail_url",
)

PRICE_KEYS = (
    "price",
    "basePrice",
    "base_price",
    "amount",
    "cost",
    "value",
    "unitPrice",
    "unit_price",
    "salePrice",
    "sale_price",
    "displayPrice",
    "display_price",
    "priceMoney",
    "price_money",
    "money",
)

ITEM_COLLECTION_KEYS = (
    "items",
    "products",
    "entries",
    "children",
    "menuItems",
    "menu_items",
    "menuEntries",
    "menu_entries",
    "productsList",
    "productList",
    "product_list",
)

SECTION_COLLECTION_KEYS = (
    "menus",
    "sections",
    "categories",
    "groups",
    "collections",
    "menuSections",
    "menu_sections",
)

MODIFIER_COLLECTION_KEYS = (
    "modifierGroups",
    "modifier_groups",
    "modifiers",
    "options",
    "choices",
    "variants",
    "addOns",
    "add_ons",
    "addons",
)


# ---------------------------------------------------------
# Provider hints
# ---------------------------------------------------------

PROVIDER_HINT_KEYS = {
    "toast": ("guid", "modifierGroups", "menus", "groups"),
    "square": ("presentment", "item_data", "modifier_list_data", "catalog"),
    "clover": ("priceMoney", "categories", "items"),
    "chownow": ("menu_url", "categories", "items"),
    "popmenu": ("menus", "sections", "items"),
    "olo": ("optionGroups", "choices", "products"),
}


# ---------------------------------------------------------
# Junk / validation
# ---------------------------------------------------------

JUNK_NAMES = {
    "home",
    "about",
    "contact",
    "locations",
    "location",
    "login",
    "sign in",
    "register",
    "account",
    "menu",
    "menus",
    "order",
    "delivery",
    "pickup",
    "cart",
    "checkout",
}

_PRICE_RANGE_RE = re.compile(
    r"^\s*[\$€£]?\s?\d{1,4}(?:[\.,]\d{1,2})?\s?-\s?[\$€£]?\s?\d{1,4}(?:[\.,]\d{1,2})?\s*$"
)

_SIMPLE_PRICE_RE = re.compile(
    r"^\s*[\$€£]?\s?\d{1,6}(?:[\.,]\d{1,2})?\s*$"
)


# ---------------------------------------------------------
# Text helpers
# ---------------------------------------------------------

def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)

    return text


def _extract_first(obj: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return None


# ---------------------------------------------------------
# Price normalization
# ---------------------------------------------------------

def _normalize_price(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:

        if isinstance(value, dict):
            for key in ("amount", "value", "price", "centAmount", "cents", "minorUnits"):
                if key in value and value[key] is not None:
                    return _normalize_price(value[key])

        if isinstance(value, str):

            text = value.strip()
            text = text.replace("$", "").replace("€", "").replace("£", "").strip()

            if not text:
                return None

            if _PRICE_RANGE_RE.match(text):
                return text

            if re.fullmatch(r"\d{3,}", text):
                num = float(text)
                if num > 100:
                    return f"{num / 100:.2f}"

            if _SIMPLE_PRICE_RE.match(text):
                return text

            return None

        if isinstance(value, (int, float)):
            num = float(value)

            if num > 100:
                num = num / 100.0

            return f"{num:.2f}"

    except Exception:
        return None

    return None


# ---------------------------------------------------------
# Field extraction
# ---------------------------------------------------------

def _extract_name(obj: Dict[str, Any]) -> Optional[str]:
    value = _extract_first(obj, NAME_KEYS)

    if isinstance(value, dict):
        value = value.get("name") or value.get("label") or value.get("title")

    text = _clean_text(value)

    if not text:
        return None

    if text.lower() in JUNK_NAMES:
        return None

    if len(text) < 2:
        return None

    return text


def _extract_description(obj: Dict[str, Any]) -> Optional[str]:
    value = _extract_first(obj, DESCRIPTION_KEYS)
    text = _clean_text(value)

    if not text:
        return None

    if len(text) > 600:
        text = text[:600].strip()

    return text


def _extract_image(obj: Dict[str, Any]) -> Optional[str]:
    value = _extract_first(obj, IMAGE_KEYS)

    if isinstance(value, dict):
        for key in ("url", "src", "imageUrl", "original", "large", "medium", "small"):
            if value.get(key):
                return _clean_text(value.get(key)) or None

    text = _clean_text(value)

    if text.startswith("http://") or text.startswith("https://"):
        return text

    return None


def _extract_price(obj: Dict[str, Any]) -> Optional[str]:
    value = _extract_first(obj, PRICE_KEYS)

    normalized = _normalize_price(value)
    if normalized is not None:
        return normalized

    offers = obj.get("offers")

    if isinstance(offers, dict):
        for key in ("price", "lowPrice", "highPrice", "amount"):
            if offers.get(key) is not None:
                return _normalize_price(offers.get(key))

    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                for key in ("price", "lowPrice", "highPrice", "amount"):
                    if offer.get(key) is not None:
                        return _normalize_price(offer.get(key))

    return None


def _extract_section_name(
    obj: Dict[str, Any],
    current_section: Optional[str],
) -> Optional[str]:
    value = _extract_first(obj, SECTION_KEYS)

    if isinstance(value, dict):
        text = _clean_text(value.get("name"))
        return text or current_section

    text = _clean_text(value)
    return text or current_section


# ---------------------------------------------------------
# Dedupe
# ---------------------------------------------------------

def _item_key(item: ExtractedMenuItem) -> str:
    return (
        f"{(item.name or '').strip().lower()}|"
        f"{(item.price or '').strip()}|"
        f"{(item.section or '').strip().lower()}"
    )


def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    seen: Set[str] = set()
    out: List[ExtractedMenuItem] = []

    for item in items:
        key = _item_key(item)

        if key in seen:
            continue

        seen.add(key)
        out.append(item)

        if len(out) >= MAX_ITEMS:
            break

    return out


# ---------------------------------------------------------
# Provider inference
# ---------------------------------------------------------

def _provider_from_payload(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None

    for provider, keys in PROVIDER_HINT_KEYS.items():
        hits = 0

        for key in keys:
            if key in data:
                hits += 1

        if hits >= 2:
            return provider

    return None


# ---------------------------------------------------------
# Item / section detection
# ---------------------------------------------------------

def _looks_like_item(obj: Dict[str, Any]) -> bool:
    name = _extract_name(obj)
    price = _extract_price(obj)

    if name and price is not None:
        return True

    if name and (
        _extract_description(obj)
        or any(key in obj for key in PRICE_KEYS)
        or "offers" in obj
    ):
        return True

    if "item_data" in obj and isinstance(obj["item_data"], dict):
        nested_name = _extract_name(obj["item_data"])
        nested_price = _extract_price(obj["item_data"])

        if nested_name and nested_price is not None:
            return True

    return False


def _looks_like_section(obj: Dict[str, Any]) -> bool:
    section_name = _extract_name(obj) or _extract_section_name(obj, None)

    if not section_name:
        return False

    for key in SECTION_COLLECTION_KEYS + ITEM_COLLECTION_KEYS:
        if isinstance(obj.get(key), list):
            return True

    return False


# ---------------------------------------------------------
# Provider-specific fast paths
# ---------------------------------------------------------

def _parse_square(data: Dict[str, Any]) -> List[ExtractedMenuItem]:
    items: List[ExtractedMenuItem] = []

    objects = data.get("objects") or data.get("catalog", {}).get("objects") or []

    if not isinstance(objects, list):
        return items

    category_names: Dict[str, str] = {}

    for obj in objects:
        if not isinstance(obj, dict):
            continue

        obj_type = _clean_text(obj.get("type")).upper()

        if obj_type == "CATEGORY":
            category_data = obj.get("category_data") or {}
            name = _clean_text(category_data.get("name"))
            obj_id = _clean_text(obj.get("id"))

            if obj_id and name:
                category_names[obj_id] = name

    for obj in objects:
        if not isinstance(obj, dict):
            continue

        obj_type = _clean_text(obj.get("type")).upper()

        if obj_type not in {"ITEM", "ITEM_VARIATION"}:
            continue

        data_node = obj.get("item_data") or obj.get("item_variation_data") or {}

        if not isinstance(data_node, dict):
            continue

        name = _extract_name(data_node)

        if not name:
            continue

        section = None
        category_id = data_node.get("category_id")

        if category_id:
            section = category_names.get(str(category_id))

        items.append(
            ExtractedMenuItem(
                name=name,
                price=_extract_price(data_node),
                section=section,
                currency="USD",
                description=_extract_description(data_node),
                image_url=_extract_image(data_node),
                provider="square",
                source_type="api",
                raw=obj,
            )
        )

        if len(items) >= MAX_ITEMS:
            break

    return items


def _parse_toast(data: Dict[str, Any]) -> List[ExtractedMenuItem]:
    items: List[ExtractedMenuItem] = []

    def walk_groups(groups: Any, current_section: Optional[str] = None) -> None:
        if not isinstance(groups, list):
            return

        for group in groups:
            if not isinstance(group, dict):
                continue

            section = _clean_text(group.get("name")) or current_section

            for item in group.get("items") or []:
                if not isinstance(item, dict):
                    continue

                name = _extract_name(item)

                if not name:
                    continue

                items.append(
                    ExtractedMenuItem(
                        name=name,
                        price=_extract_price(item),
                        section=section,
                        currency="USD",
                        description=_extract_description(item),
                        image_url=_extract_image(item),
                        provider="toast",
                        source_type="api",
                        raw=item,
                    )
                )

                if len(items) >= MAX_ITEMS:
                    return

                for modifier_group in item.get("modifierGroups") or []:
                    if not isinstance(modifier_group, dict):
                        continue

                    for mod in modifier_group.get("items") or []:
                        if not isinstance(mod, dict):
                            continue

                        mod_name = _extract_name(mod)

                        if not mod_name:
                            continue

                        items.append(
                            ExtractedMenuItem(
                                name=mod_name,
                                price=_extract_price(mod),
                                section=section,
                                currency="USD",
                                description=_extract_description(mod),
                                provider="toast",
                                source_type="api",
                                raw=mod,
                            )
                        )

                        if len(items) >= MAX_ITEMS:
                            return

            walk_groups(group.get("groups") or [], section)

    walk_groups(data.get("groups") or [])

    for menu in data.get("menus") or []:
        if len(items) >= MAX_ITEMS:
            break

        if isinstance(menu, dict):
            walk_groups(menu.get("groups") or [])

    return items


def _parse_clover(data: Dict[str, Any]) -> List[ExtractedMenuItem]:
    items: List[ExtractedMenuItem] = []

    def walk(node: Any, section: Optional[str] = None) -> None:
        if len(items) >= MAX_ITEMS:
            return

        if isinstance(node, list):
            for value in node:
                walk(value, section)
            return

        if not isinstance(node, dict):
            return

        next_section = section

        if "name" in node and isinstance(node.get("items"), list):
            next_section = _clean_text(node.get("name")) or section

        if _looks_like_item(node):
            name = _extract_name(node)

            if name:
                items.append(
                    ExtractedMenuItem(
                        name=name,
                        price=_extract_price(node),
                        section=_extract_section_name(node, next_section),
                        currency="USD",
                        description=_extract_description(node),
                        image_url=_extract_image(node),
                        provider="clover",
                        source_type="api",
                        raw=node,
                    )
                )

        for value in node.values():
            if isinstance(value, (list, dict)):
                walk(value, next_section)

    walk(data)

    return items


# ---------------------------------------------------------
# Generic recursive parser
# ---------------------------------------------------------

def _scan(
    data: Any,
    *,
    items: List[ExtractedMenuItem],
    current_section: Optional[str] = None,
    provider: Optional[str] = None,
    source_type: str = "api",
    depth: int = 0,
) -> None:
    if depth > MAX_RECURSION_DEPTH:
        return

    if len(items) >= MAX_ITEMS:
        return

    if isinstance(data, list):
        for value in data:
            _scan(
                value,
                items=items,
                current_section=current_section,
                provider=provider,
                source_type=source_type,
                depth=depth + 1,
            )
        return

    if not isinstance(data, dict):
        return

    next_section = current_section

    if _looks_like_section(data):
        candidate_section = _extract_name(data) or _extract_section_name(data, current_section)

        if candidate_section:
            next_section = candidate_section

    if "item_data" in data and isinstance(data["item_data"], dict):
        nested = data["item_data"]

        if _looks_like_item(nested):
            name = _extract_name(nested)

            if name:
                items.append(
                    ExtractedMenuItem(
                        name=name,
                        price=_extract_price(nested),
                        section=_extract_section_name(nested, next_section),
                        currency="USD",
                        description=_extract_description(nested),
                        image_url=_extract_image(nested),
                        provider=provider,
                        source_type=source_type,
                        raw=data,
                    )
                )

                if len(items) >= MAX_ITEMS:
                    return

    if _looks_like_item(data):
        name = _extract_name(data)

        if name:
            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=_extract_price(data),
                    section=_extract_section_name(data, next_section),
                    currency="USD",
                    description=_extract_description(data),
                    image_url=_extract_image(data),
                    provider=provider,
                    source_type=source_type,
                    raw=data,
                )
            )

            if len(items) >= MAX_ITEMS:
                return

    for key in SECTION_COLLECTION_KEYS:
        value = data.get(key)

        if isinstance(value, list):
            _scan(
                value,
                items=items,
                current_section=next_section,
                provider=provider,
                source_type=source_type,
                depth=depth + 1,
            )

    for key in ITEM_COLLECTION_KEYS:
        value = data.get(key)

        if isinstance(value, list):
            _scan(
                value,
                items=items,
                current_section=next_section,
                provider=provider,
                source_type=source_type,
                depth=depth + 1,
            )

    for key in MODIFIER_COLLECTION_KEYS:
        value = data.get(key)

        if isinstance(value, list):
            _scan(
                value,
                items=items,
                current_section=next_section,
                provider=provider,
                source_type=source_type,
                depth=depth + 1,
            )

    for value in data.values():
        if isinstance(value, (dict, list)):
            _scan(
                value,
                items=items,
                current_section=next_section,
                provider=provider,
                source_type=source_type,
                depth=depth + 1,
            )


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def parse_universal_menu_json(
    data: Any,
    *,
    provider_hint: Optional[str] = None,
    source_type: str = "api",
) -> List[ExtractedMenuItem]:
    """
    Parse arbitrary restaurant/provider JSON into ExtractedMenuItem objects.

    Supports:
    - Toast-style nested menus/groups/items
    - Square catalog/item_data structures
    - Clover/ChowNow/Popmenu/Olo-like category/item payloads
    - Generic GraphQL / REST menu responses
    """

    if data is None:
        return []

    provider = provider_hint

    if provider is None and isinstance(data, dict):
        provider = _provider_from_payload(data)

    try:

        if provider == "toast" and isinstance(data, dict):
            items = _parse_toast(data)
            items = _dedupe(items)

            for item in items:
                item.source_type = source_type

            if items:
                logger.info(
                    "universal_menu_json_parsed provider=%s items=%s",
                    provider,
                    len(items),
                )

            return items[:MAX_ITEMS]

        if provider == "square" and isinstance(data, dict):
            items = _parse_square(data)
            items = _dedupe(items)

            for item in items:
                item.source_type = source_type

            if items:
                logger.info(
                    "universal_menu_json_parsed provider=%s items=%s",
                    provider,
                    len(items),
                )

            return items[:MAX_ITEMS]

        if provider == "clover" and isinstance(data, dict):
            items = _parse_clover(data)
            items = _dedupe(items)

            for item in items:
                item.source_type = source_type

            if items:
                logger.info(
                    "universal_menu_json_parsed provider=%s items=%s",
                    provider,
                    len(items),
                )

            return items[:MAX_ITEMS]

        items: List[ExtractedMenuItem] = []

        _scan(
            data,
            items=items,
            current_section=None,
            provider=provider,
            source_type=source_type,
            depth=0,
        )

        items = _dedupe(items)

        for item in items:
            item.source_type = source_type

            if provider and not item.provider:
                item.provider = provider

        if items:
            logger.info(
                "universal_menu_json_parsed provider=%s items=%s",
                provider,
                len(items),
            )

        return items[:MAX_ITEMS]

    except Exception as exc:
        logger.debug(
            "universal_menu_json_parse_failed provider=%s error=%s",
            provider,
            exc,
        )
        return []