from typing import Any, Dict, List, Optional


# =========================================================
# ENTRYPOINT
# =========================================================

def parse_grubhub_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    content = (
        payload.get("object", {})
        .get("data", {})
        .get("content", [])
    )

    for entry in content:
        entity = entry.get("entity")
        if not entity:
            continue

        parse_type = _classify_payload(entity)

        if parse_type == "recommendation_noise":
            continue

        item = _parse_core_item(entity, parse_type)
        items.append(item)

    return items


# =========================================================
# CLASSIFICATION (FIXED + ROBUST)
# =========================================================

def _classify_payload(entity: Dict[str, Any]) -> str:
    if not entity:
        return "unsupported_unknown"

    # ✅ PRIMARY: grubhub listing / preview items
    if entity.get("item_id") and entity.get("item_name"):
        if entity.get("item_price"):
            return "configurable_preview"

    # full item detail payload
    if "choice_category_list" in entity:
        if entity.get("price", {}).get("amount") == 0:
            return "combo_recursive"
        return "full_item_detail"

    # simple item (no modifiers)
    if entity.get("quick_add_available") and not entity.get("choice_option_ids_map"):
        return "simple_item"

    return "unsupported_unknown"


# =========================================================
# CORE PARSER
# =========================================================

def _parse_core_item(entity: Dict[str, Any], parse_type: str) -> Dict[str, Any]:
    price_data = _extract_price_bundle(entity)

    return {
        "provider": "grubhub",

        "provider_item_id": _safe_str(entity.get("item_id") or entity.get("id")),
        "provider_restaurant_id": _safe_str(entity.get("restaurant_id")),
        "provider_category_id": _safe_str(entity.get("menu_category_id")),
        "provider_category_name": entity.get("menu_category_name"),

        "name": entity.get("item_name") or entity.get("name"),
        "description": entity.get("item_description") or entity.get("description"),

        # pricing
        "currency": price_data["currency"],
        "base_price_cents": price_data["base"],
        "min_price_cents": price_data["min"],
        "max_price_cents": price_data["max"],
        "price_display": price_data["display"],
        "pickup_price_cents": price_data["pickup"],
        "delivery_price_cents": price_data["delivery"],

        # config flags
        "has_required_options": _has_required_options(entity),
        "required_price_with_choice_options": _safe_bool(
            entity.get("item_price", {}).get("required_price_with_choice_options")
        ),

        "quick_add_available": _safe_bool(entity.get("quick_add_available")),
        "quick_add_state": entity.get("quick_add_state"),

        "requires_configuration": _requires_configuration(entity),
        "is_price_final": _is_price_final(entity),

        # availability
        "is_available": _safe_bool(entity.get("available")),

        # features
        "is_popular": _extract_popular(entity),
        "is_spicy": _extract_spicy(entity),
        "badges": _extract_badges(entity),

        # images
        "image_url": _extract_primary_image(entity),
        "image_urls": _extract_all_images(entity),

        # metadata
        "parse_type": parse_type,

        # modifiers (pass 2)
        "modifiers_loaded": False,
        "modifier_groups": [],
        "modifier_summary": {
            "group_count": 0,
            "option_count": 0,
            "max_depth": 0,
            "has_quantity_rules": False,
            "has_nested_groups": False,
        },

        # warnings
        "parse_warnings": _collect_warnings(entity, parse_type),

        # raw fallback
        "raw_payload": entity,
    }


# =========================================================
# PRICE EXTRACTION (SAFE + FALLBACKS)
# =========================================================

def _extract_price_bundle(entity: Dict[str, Any]) -> Dict[str, Any]:
    base = None
    pickup = None
    delivery = None
    currency = "USD"
    display = None

    item_price = entity.get("item_price", {})

    if item_price:
        pickup_data = item_price.get("pickup", {})
        delivery_data = item_price.get("delivery", {})

        pickup = pickup_data.get("value")
        delivery = delivery_data.get("value")

        base = pickup or delivery
        currency = pickup_data.get("currency", currency)
        display = pickup_data.get("styled_text", {}).get("text")

    if base is None:
        base = entity.get("price", {}).get("amount")

    min_price = entity.get("minimum_price_variation", {}).get("amount", base)
    max_price = entity.get("maximum_price_variation", {}).get("amount", base)

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
    return bool(
        entity.get("item_price", {}).get("has_costing_required_options")
        or entity.get("choice_option_ids_map")
    )


def _is_price_final(entity: Dict[str, Any]) -> bool:
    if entity.get("item_price", {}).get("has_costing_required_options"):
        return False

    if entity.get("choice_option_ids_map"):
        return False

    if entity.get("price", {}).get("amount") == 0:
        return False

    return True


# =========================================================
# FEATURES
# =========================================================

def _extract_popular(entity: Dict[str, Any]) -> bool:
    return bool(
        entity.get("features_v2", {}).get("POPULAR", {}).get("enabled")
        or entity.get("features", {}).get("POPULAR")
    )


def _extract_spicy(entity: Dict[str, Any]) -> bool:
    return bool(
        entity.get("features_v2", {}).get("SPICY", {}).get("enabled")
        or entity.get("features", {}).get("SPICY")
    )


def _extract_badges(entity: Dict[str, Any]) -> List[str]:
    badges = []

    if _extract_popular(entity):
        badges.append("Popular")

    if _extract_spicy(entity):
        badges.append("Spicy")

    return badges


# =========================================================
# IMAGES (SAFE BUILD)
# =========================================================

def _extract_primary_image(entity: Dict[str, Any]) -> Optional[str]:
    images = entity.get("media_images") or []
    if images:
        img = images[0]
        return _build_image_url(img)
    return None


def _extract_all_images(entity: Dict[str, Any]) -> List[str]:
    images = entity.get("media_images") or []
    return [_build_image_url(img) for img in images if img]


def _build_image_url(img: Dict[str, Any]) -> Optional[str]:
    base = img.get("base_url")
    public_id = img.get("public_id")
    fmt = img.get("format")

    if base and public_id and fmt:
        return f"{base}{public_id}.{fmt}"
    return None


# =========================================================
# WARNINGS
# =========================================================

def _collect_warnings(entity: Dict[str, Any], parse_type: str) -> List[str]:
    warnings: List[str] = []

    if parse_type == "configurable_preview" and entity.get("choice_option_ids_map"):
        if not entity.get("choice_option_data_map"):
            warnings.append("modifier_definitions_missing")

    if parse_type == "unsupported_unknown":
        warnings.append("unsupported_payload_shape")

    return warnings


# =========================================================
# SAFE HELPERS
# =========================================================

def _safe_str(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def _safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)