from __future__ import annotations

from typing import Any, Dict, List, Optional


# =========================================================
# ENTRYPOINT
# =========================================================

def parse_grubhub_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if not isinstance(payload, dict):
        return items

    content = _extract_content(payload)

    for entry in content:
        if not isinstance(entry, dict):
            continue

        entity = entry.get("entity")
        if not isinstance(entity, dict):
            continue

        parse_type = _classify_payload(entity)

        if parse_type in {"recommendation_noise", "unsupported_unknown"}:
            continue

        item = _parse_core_item(entity, parse_type)

        # 🔥 HARD FILTER (CRITICAL)
        if not item.get("name"):
            continue

        items.append(item)

    return items


# =========================================================
# ROOT EXTRACTION
# =========================================================

def _extract_content(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    object_block = payload.get("object")
    if isinstance(object_block, dict):
        data_block = object_block.get("data")
        if isinstance(data_block, dict):
            content = data_block.get("content")
            if isinstance(content, list):
                return content

    content = payload.get("content")
    if isinstance(content, list):
        return content

    entity = payload.get("entity")
    if isinstance(entity, dict):
        return [{"entity": entity}]

    if "item_id" in payload or "id" in payload:
        return [{"entity": payload}]

    return []


# =========================================================
# CLASSIFICATION
# =========================================================

def _classify_payload(entity: Dict[str, Any]) -> str:
    if not entity:
        return "unsupported_unknown"

    has_preview_identity = bool(entity.get("item_id") and entity.get("item_name"))
    has_detail_identity = bool(entity.get("id") and entity.get("name"))
    has_item_price = isinstance(entity.get("item_price"), dict)
    has_choice_map = bool(entity.get("choice_option_ids_map"))
    has_choice_categories = isinstance(entity.get("choice_category_list"), list)

    if has_preview_identity and has_item_price:
        if has_choice_map or has_choice_categories:
            return "configurable_preview"
        return "simple_item"

    if has_detail_identity:
        if has_choice_categories:
            price_amount = _safe_int(entity.get("price", {}).get("amount"))
            if price_amount == 0:
                return "combo_recursive"
        return "full_item_detail"

    if has_preview_identity:
        return "simple_item"

    return "unsupported_unknown"


# =========================================================
# CORE PARSER (🔥 CRITICAL FIXES HERE)
# =========================================================

def _parse_core_item(entity: Dict[str, Any], parse_type: str) -> Dict[str, Any]:
    price_data = _extract_price_bundle(entity)

    name = _safe_str(entity.get("item_name") or entity.get("name"))

    return {
        "provider": "grubhub",

        "provider_item_id": _safe_str(entity.get("item_id") or entity.get("id")),
        "provider_restaurant_id": _safe_str(entity.get("restaurant_id")),
        "provider_category_id": _safe_str(entity.get("menu_category_id")),

        # 🔥 IMPORTANT FIX (prevents adapter empty)
        "provider_category_name": _safe_str(entity.get("menu_category_name")) or "uncategorized",

        "name": name,
        "description": _safe_str(entity.get("item_description") or entity.get("description")),

        # PRICE (adapter depends on this)
        "currency": price_data["currency"],
        "base_price_cents": price_data["base"],
        "min_price_cents": price_data["min"],
        "max_price_cents": price_data["max"],

        "price_display": price_data["display"],
        "pickup_price_cents": price_data["pickup"],
        "delivery_price_cents": price_data["delivery"],

        # FLAGS
        "has_required_options": _has_required_options(entity),
        "requires_configuration": _requires_configuration(entity),
        "is_price_final": _is_price_final(entity),
        "is_available": _safe_bool(entity.get("available")),

        # FEATURES
        "is_popular": _extract_popular(entity),
        "is_spicy": _extract_spicy(entity),
        "badges": _extract_badges(entity),

        # MEDIA
        "image_url": _extract_primary_image(entity),
        "image_urls": _extract_all_images(entity),

        # PARSER META
        "parse_type": parse_type,
        "parse_warnings": _collect_warnings(entity, parse_type),

        # PIPELINE REQUIRED
        "modifiers_loaded": False,
        "modifier_groups": [],
        "modifier_summary": {
            "group_count": 0,
            "option_count": 0,
            "max_depth": 0,
            "has_quantity_rules": False,
            "has_nested_groups": False,
        },

        "raw_payload": entity,
    }


# =========================================================
# PRICE EXTRACTION (🔥 HARDENED)
# =========================================================

def _extract_price_bundle(entity: Dict[str, Any]) -> Dict[str, Any]:
    base = None
    pickup = None
    delivery = None
    currency = "USD"
    display = None

    item_price = entity.get("item_price", {})

    if isinstance(item_price, dict):
        pickup_data = item_price.get("pickup", {})
        delivery_data = item_price.get("delivery", {})

        if isinstance(pickup_data, dict):
            pickup = _safe_int(pickup_data.get("value"))
            currency = _safe_str(pickup_data.get("currency")) or currency
            display = _safe_str(pickup_data.get("styled_text", {}).get("text"))

        if isinstance(delivery_data, dict):
            delivery = _safe_int(delivery_data.get("value"))

        base = pickup if pickup is not None else delivery

    # fallback
    if base is None:
        base = _safe_int(entity.get("price", {}).get("amount"))

    # 🔥 CRITICAL: ensure adapter never gets None
    base = base if base is not None else 0

    min_price = _safe_int(entity.get("minimum_price_variation", {}).get("amount")) or base
    max_price = _safe_int(entity.get("maximum_price_variation", {}).get("amount")) or base

    return {
        "base": base,
        "min": min_price,
        "max": max_price,
        "pickup": pickup,
        "delivery": delivery,
        "currency": currency,
        "display": display,
    }


# =========================================================
# FLAGS
# =========================================================

def _has_required_options(entity: Dict[str, Any]) -> bool:
    return bool(
        entity.get("item_price", {}).get("has_costing_required_options")
        or entity.get("choice_option_ids_map")
        or entity.get("choice_category_list")
    )


def _requires_configuration(entity: Dict[str, Any]) -> bool:
    return _has_required_options(entity)


def _is_price_final(entity: Dict[str, Any]) -> bool:
    if _has_required_options(entity):
        return False

    price_amount = _safe_int(entity.get("price", {}).get("amount"))
    if price_amount == 0 and entity.get("minimum_price_variation"):
        return False

    return True


# =========================================================
# FEATURES
# =========================================================

def _extract_popular(entity: Dict[str, Any]) -> bool:
    return bool(entity.get("features_v2", {}).get("POPULAR", {}).get("enabled"))


def _extract_spicy(entity: Dict[str, Any]) -> bool:
    return bool(entity.get("features_v2", {}).get("SPICY", {}).get("enabled"))


def _extract_badges(entity: Dict[str, Any]) -> List[str]:
    badges: List[str] = []
    if _extract_popular(entity):
        badges.append("Popular")
    if _extract_spicy(entity):
        badges.append("Spicy")
    return badges


# =========================================================
# IMAGES
# =========================================================

def _extract_primary_image(entity: Dict[str, Any]) -> Optional[str]:
    images = entity.get("media_images")
    if isinstance(images, list) and images:
        return _build_image_url(images[0])

    return _build_image_url(entity.get("media_image"))


def _extract_all_images(entity: Dict[str, Any]) -> List[str]:
    urls: List[str] = []

    images = entity.get("media_images")
    if isinstance(images, list):
        for img in images:
            url = _build_image_url(img)
            if url:
                urls.append(url)

    if not urls:
        url = _build_image_url(entity.get("media_image"))
        if url:
            urls.append(url)

    return urls


def _build_image_url(img: Any) -> Optional[str]:
    if not isinstance(img, dict):
        return None

    base = _safe_str(img.get("base_url"))
    public_id = _safe_str(img.get("public_id"))
    fmt = _safe_str(img.get("format"))

    if not base or not public_id or not fmt:
        return None

    if not base.endswith("/"):
        base += "/"

    return f"{base}{public_id}.{fmt}"


# =========================================================
# WARNINGS
# =========================================================

def _collect_warnings(entity: Dict[str, Any], parse_type: str) -> List[str]:
    warnings: List[str] = []

    if parse_type == "configurable_preview" and entity.get("choice_option_ids_map"):
        if not entity.get("choice_option_data_map"):
            warnings.append("modifier_definitions_missing")

    if parse_type == "full_item_detail" and not entity.get("choice_category_list"):
        warnings.append("detail_without_choice_categories")

    if parse_type == "combo_recursive" and not entity.get("choice_category_list"):
        warnings.append("combo_without_choice_categories")

    return warnings


# =========================================================
# SAFE HELPERS
# =========================================================

def _safe_str(value: Any) -> Optional[str]:
    try:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None
    except Exception:
        return None


def _safe_bool(value: Any) -> Optional[bool]:
    return bool(value) if value is not None else None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None