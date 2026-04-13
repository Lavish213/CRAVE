from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

DEFAULT_SOURCE = "toast"
DEFAULT_CONFIDENCE = 0.95
MAX_ITEMS = 5000


@dataclass(slots=True)
class ToastRestaurantInput:
    city_id: str
    source_url: Optional[str] = None
    confidence: float = DEFAULT_CONFIDENCE


@dataclass(slots=True)
class ToastIngestResult:
    restaurant_guid: Optional[str]
    restaurant_name: Optional[str]
    source_url: Optional[str]
    item_count: int
    written_count: int
    skipped_count: int


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_price(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None

        if isinstance(value, list):
            if not value:
                return None
            value = value[0]

        numeric = float(value)

        if numeric > 100:
            return round(numeric / 100, 2)

        return round(numeric, 2)
    except Exception:
        return None


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        cleaned = str(value).strip()
        return cleaned or None
    except Exception:
        return None


def _build_address(location: dict) -> Optional[str]:
    if not isinstance(location, dict):
        return None

    parts = [
        location.get("address1"),
        location.get("address2"),
        location.get("city"),
        location.get("state"),
        location.get("zip") or location.get("zipcode"),
    ]

    cleaned = [_clean_str(part) for part in parts]
    cleaned = [part for part in cleaned if part]

    return ", ".join(cleaned) if cleaned else None


def _extract_docs(payloads: Sequence[Any]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []

    for payload in payloads:
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and isinstance(item.get("data"), dict):
                    docs.append(item["data"])
        elif isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            docs.append(payload["data"])

    return docs


def _find_restaurant(docs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    for doc in docs:
        restaurant = doc.get("restaurantV2")
        if isinstance(restaurant, dict):
            return restaurant

        cart_restaurant = doc.get("cartV2", {}).get("cart", {}).get("restaurant")
        if isinstance(cart_restaurant, dict):
            return cart_restaurant

        ranked_offers = doc.get("offers", {}).get("rankedPromoOffers")
        if isinstance(ranked_offers, dict) and ranked_offers.get("restaurantGuid"):
            return {
                "guid": ranked_offers.get("restaurantGuid"),
                "name": None,
                "location": {},
                "shortUrl": None,
            }

    raise ValueError("NO_RESTAURANT")


def _derive_source_url(
    restaurant: Dict[str, Any],
    restaurant_input: ToastRestaurantInput,
) -> Optional[str]:
    if restaurant_input.source_url:
        return restaurant_input.source_url

    short_url = restaurant.get("shortUrl")
    if short_url:
        return f"https://www.toasttab.com/{short_url}/v3"

    return None


def _extract_image(item: Dict[str, Any]) -> Optional[str]:
    image_urls = item.get("imageUrls") or {}
    if isinstance(image_urls, dict):
        return (
            image_urls.get("small")
            or image_urls.get("medium")
            or image_urls.get("large")
            or image_urls.get("raw")
        )

    image = item.get("image") or {}
    if isinstance(image, dict):
        return image.get("displaySrc") or image.get("src")

    photos = item.get("photos")
    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            return first.get("displaySrc") or first.get("src")

    return None


def _extract_menu_item_price(item: Dict[str, Any]) -> Optional[float]:
    price = _safe_price(item.get("price"))
    if price is not None:
        return price

    pricing = item.get("pricing") or {}
    if isinstance(pricing, dict):
        amount = _safe_price(pricing.get("price") or pricing.get("amount"))
        if amount is not None:
            return amount

    prices = item.get("prices")
    amount = _safe_price(prices)
    if amount is not None:
        return amount

    variants = item.get("variants") or []
    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, dict):
                continue

            variant_pricing = variant.get("pricing") or {}
            if isinstance(variant_pricing, dict):
                amount = _safe_price(
                    variant_pricing.get("price") or variant_pricing.get("amount")
                )
                if amount is not None:
                    return amount

    price_levels = item.get("priceLevels") or []
    if isinstance(price_levels, list):
        for level in price_levels:
            if not isinstance(level, dict):
                continue

            amount = _safe_price(level.get("price"))
            if amount is not None:
                return amount

    price_range = item.get("priceRange") or {}
    if isinstance(price_range, dict):
        amount = _safe_price(price_range.get("min"))
        if amount is not None:
            return amount

    return None


def _extract_candidate_from_menu_item(
    *,
    item: Dict[str, Any],
    address: Optional[str],
    city_id: str,
    lat: Optional[float],
    lng: Optional[float],
    phone: Optional[str],
    source_url: Optional[str],
    confidence: float,
) -> Optional[Dict[str, Any]]:
    item_guid = _clean_str(item.get("guid"))
    name = _clean_str(item.get("name"))

    if not item_guid or not name:
        return None

    image = _extract_image(item)
    price = _extract_menu_item_price(item)

    raw_payload = dict(item)
    raw_payload["normalized_price"] = price
    raw_payload["normalized_image"] = image
    raw_payload["normalized_address"] = address
    raw_payload["normalized_phone"] = phone
    raw_payload["normalized_website"] = source_url

    return {
        "external_id": item_guid,
        "source": DEFAULT_SOURCE,
        "name": name,
        "address": address,
        "city_id": city_id,
        "lat": lat,
        "lng": lng,
        "phone": _clean_str(phone),
        "website": source_url,
        "confidence": confidence,
        "raw_payload": raw_payload,
    }


def _extract(
    payloads: Sequence[Any],
    restaurant_input: ToastRestaurantInput,
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str], Optional[str]]:
    docs = _extract_docs(payloads)

    if not docs:
        raise ValueError("NO_GRAPHQL_DATA")

    restaurant = _find_restaurant(docs)

    restaurant_guid = _clean_str(restaurant.get("guid"))
    restaurant_name = _clean_str(restaurant.get("name"))

    location = restaurant.get("location") or {}
    lat = _safe_float(location.get("latitude") or location.get("lat"))
    lng = _safe_float(location.get("longitude") or location.get("lng") or location.get("long"))
    address = _build_address(location)
    phone = _clean_str(location.get("phone") or location.get("phoneNumber"))

    source_url = _derive_source_url(restaurant, restaurant_input)

    candidates: List[Dict[str, Any]] = []
    seen_item_guids = set()

    for doc in docs:
        item = doc.get("menuItemDetails")

        if not isinstance(item, dict):
            continue

        candidate = _extract_candidate_from_menu_item(
            item=item,
            address=address,
            city_id=restaurant_input.city_id,
            lat=lat,
            lng=lng,
            phone=phone,
            source_url=source_url,
            confidence=restaurant_input.confidence,
        )

        if not candidate:
            continue

        external_id = candidate["external_id"]
        if external_id in seen_item_guids:
            continue

        seen_item_guids.add(external_id)
        candidates.append(candidate)

        if len(candidates) >= MAX_ITEMS:
            logger.warning(
                "toast_ingest_max_items_reached limit=%s restaurant_guid=%s",
                MAX_ITEMS,
                restaurant_guid,
            )
            break

    if not candidates:
        raise ValueError("NO_MENU_ITEMS_FOUND")

    return candidates, restaurant_guid, restaurant_name, source_url


def _write(candidates: List[Dict[str, Any]]) -> int:
    from app.services.ingest.candidate_writer import CandidateWriter

    writer = CandidateWriter()
    written = writer.write(candidates)

    return written or 0


def ingest_toast_json_strings(
    *,
    db,
    restaurant_input: ToastRestaurantInput,
    payload_strings: Sequence[str],
) -> ToastIngestResult:
    if not restaurant_input.city_id:
        raise ValueError("MISSING_CITY_ID")

    if not payload_strings:
        raise ValueError("NO_PAYLOAD_STRINGS")

    payloads: List[Any] = []

    for payload_string in payload_strings:
        if not payload_string:
            continue

        payload_string = payload_string.strip()
        if not payload_string:
            continue

        try:
            payloads.append(json.loads(payload_string))
        except json.JSONDecodeError as exc:
            logger.warning("toast_ingest_bad_json error=%s", exc)

    if not payloads:
        raise ValueError("NO_VALID_JSON_PAYLOADS")

    candidates, guid, name, url = _extract(payloads, restaurant_input)

    _ = db

    written = _write(candidates)

    logger.info(
        "toast_ingest_complete guid=%s name=%s items=%s written=%s skipped=%s",
        guid,
        name,
        len(candidates),
        written,
        max(len(candidates) - written, 0),
    )

    return ToastIngestResult(
        restaurant_guid=guid,
        restaurant_name=name,
        source_url=url,
        item_count=len(candidates),
        written_count=written,
        skipped_count=max(len(candidates) - written, 0),
    )