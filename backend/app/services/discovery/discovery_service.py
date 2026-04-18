from __future__ import annotations

import logging
import math
import re
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.category import Category
from app.db.models.city import City
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery.candidate_store_v2 import upsert_discovery_candidate_v2


logger = logging.getLogger(__name__)


DEFAULT_SOURCE = "unknown"
DEFAULT_CONFIDENCE = 0.5
MIN_CITY_MATCH_SCORE = 0.65

_CATEGORY_ALIASES = {
    "burger": "burgers",
    "burgers": "burgers",
    "pizza": "pizza",
    "pizza_restaurant": "pizza",
    "mexican": "mexican",
    "taqueria": "mexican",
    "tacos": "mexican",
    "tex-mex": "mexican",
    "tex_mex": "mexican",
    "mexican_restaurant": "mexican",
    "chinese": "chinese",
    "chinese_restaurant": "chinese",
    "dim_sum": "chinese",
    "dim sum": "chinese",
    "cantonese": "chinese",
    "szechuan": "chinese",
    "japanese": "japanese",
    "sushi": "japanese",
    "ramen": "japanese",
    "japanese_restaurant": "japanese",
    "sushi_restaurant": "japanese",
    "ramen_restaurant": "japanese",
    "thai": "thai",
    "thai_restaurant": "thai",
    "vietnamese": "vietnamese",
    "pho": "vietnamese",
    "vietnamese_restaurant": "vietnamese",
    "indian": "indian",
    "indian_restaurant": "indian",
    "curry": "indian",
    "mediterranean": "mediterranean",
    "middle eastern": "mediterranean",
    "middle_eastern": "mediterranean",
    "kebab": "mediterranean",
    "greek": "mediterranean",
    "turkish": "mediterranean",
    "lebanese": "mediterranean",
    "falafel": "mediterranean",
    "mediterranean_restaurant": "mediterranean",
    "french": "mediterranean",
    "french_restaurant": "mediterranean",
    "spanish": "mediterranean",
    "peruvian": "mediterranean",
    "ethiopian": "mediterranean",
    "african": "mediterranean",
    "bbq": "bbq",
    "barbecue": "bbq",
    "barbecue_restaurant": "bbq",
    "smokehouse": "bbq",
    "seafood": "seafood",
    "seafood_restaurant": "seafood",
    "fish": "seafood",
    "fish_and_chips": "seafood",
    "steak": "american",
    "steakhouse": "american",
    "american": "american",
    "american_restaurant": "american",
    "diner": "american",
    "sandwich": "american",
    "sandwich_shop": "american",
    "hot_dog": "american",
    "wings": "american",
    "caribbean": "american",
    "soul_food": "american",
    "southern": "american",
    "cafe": "cafe",
    "coffee": "coffee",
    "coffee_shop": "coffee",
    "tea": "coffee",
    "tea_house": "coffee",
    "bubble_tea": "coffee",
    "cafe_restaurant": "cafe",
    "bakery": "bakery",
    "pastry": "bakery",
    "patisserie": "bakery",
    "dessert": "desserts",
    "desserts": "desserts",
    "ice_cream": "desserts",
    "ice cream": "desserts",
    "frozen_yogurt": "desserts",
    "donut": "desserts",
    "donuts": "desserts",
    "dessert_shop": "desserts",
    "food truck": "restaurant",
    "food trucks": "restaurant",
    "food_truck": "restaurant",
    "restaurant": "restaurant",
    "restaurants": "restaurant",
    "fast food": "fast casual",
    "fast_food": "fast casual",
    "fast_food_restaurant": "fast casual",
    "meal_takeaway": "fast casual",
    "fast casual": "fast casual",
    "fast_casual": "fast casual",
    "korean": "korean",
    "korean_restaurant": "korean",
    "bulgogi": "korean",
    "italian": "italian",
    "italian_restaurant": "italian",
    "pasta": "italian",
    "brunch": "breakfast",
    "breakfast": "breakfast",
    "breakfast_restaurant": "breakfast",
    "brunch_restaurant": "breakfast",
    "vegan": "vegan",
    "vegetarian": "vegan",
    "vegetarian_restaurant": "vegan",
    "vegan_restaurant": "vegan",
    "bar": "bar",
    "pub": "bar",
    "wine_bar": "bar",
    "sports_bar": "bar",
    "night_club": "bar",
    "cocktail_bar": "bar",
    "beer_garden": "bar",
    "biergarten": "bar",
    "halal": "halal",
    "kosher": "kosher",
    "fine_dining": "fine dining",
    "fine dining": "fine dining",
    "upscale": "fine dining",
    "bistro": "fine dining",
}


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        cleaned = str(value).strip()
        return cleaned or None
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _clamp_confidence(value: Any) -> float:
    parsed = _safe_float(value)
    if parsed is None:
        return DEFAULT_CONFIDENCE
    if parsed < 0.0:
        return 0.0
    if parsed > 1.0:
        return 1.0
    return parsed


def _normalize_name(name: Any) -> Optional[str]:
    cleaned = _clean(name)
    if not cleaned:
        return None
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _normalize_slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _tokenize(value: str) -> list[str]:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    return [part for part in value.split() if part]


def _best_city_from_address(*, db: Session, address: Optional[str]) -> Optional[City]:
    if not address:
        return None

    lowered = address.lower()
    cities = db.query(City).all()

    best_city: Optional[City] = None
    best_score = 0.0

    for city in cities:
        name = _clean(getattr(city, "name", None))
        slug = _clean(getattr(city, "slug", None))
        score = 0.0

        if name and name.lower() in lowered:
            score = max(score, 1.0)

        if slug:
            slug_text = slug.replace("-", " ").lower()
            if slug_text and slug_text in lowered:
                score = max(score, 0.95)

        if score > best_score:
            best_city = city
            best_score = score

    if best_score >= MIN_CITY_MATCH_SCORE:
        return best_city

    return None


def _distance_score(city_lat, city_lng, lat, lng) -> float:
    if city_lat is None or city_lng is None:
        return float("inf")
    return math.sqrt((city_lat - lat) ** 2 + (city_lng - lng) ** 2)


def _nearest_city_from_coords(*, db: Session, lat: Optional[float], lng: Optional[float]) -> Optional[City]:
    if lat is None or lng is None:
        return None

    cities = db.query(City).all()
    best_city: Optional[City] = None
    best_distance = float("inf")

    for city in cities:
        city_lat = _safe_float(getattr(city, "lat", None))
        city_lng = _safe_float(getattr(city, "lng", None))
        distance = _distance_score(city_lat, city_lng, lat, lng)
        if distance < best_distance:
            best_distance = distance
            best_city = city

    return best_city


def _resolve_city(
    *,
    db: Session,
    city_id: Optional[str] = None,
    city_slug: Optional[str] = None,
    city_name: Optional[str] = None,
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> Optional[City]:
    clean_city_id = _clean(city_id)
    if clean_city_id:
        city = db.query(City).filter(City.id == clean_city_id).one_or_none()
        if city:
            return city

    clean_city_slug = _clean(city_slug)
    if clean_city_slug:
        normalized_slug = _normalize_slug(clean_city_slug)
        city = (
            db.query(City)
            .filter(func.lower(City.slug) == normalized_slug.lower())
            .one_or_none()
        )
        if city:
            return city

    clean_city_name = _clean(city_name)
    if clean_city_name:
        city = (
            db.query(City)
            .filter(func.lower(City.name) == clean_city_name.lower())
            .one_or_none()
        )
        if city:
            return city

    city = _best_city_from_address(db=db, address=address)
    if city:
        return city

    return _nearest_city_from_coords(db=db, lat=lat, lng=lng)


def _resolve_category(
    *,
    db: Session,
    category_id: Optional[str] = None,
    category_hint: Optional[str] = None,
) -> Optional[Category]:
    clean_category_id = _clean(category_id)
    if clean_category_id:
        category = db.query(Category).filter(Category.id == clean_category_id).one_or_none()
        if category:
            return category

    clean_hint = _clean(category_hint)
    if not clean_hint:
        return None

    hint = clean_hint.lower().strip()

    alias_target = (
        _CATEGORY_ALIASES.get(hint)
        or _CATEGORY_ALIASES.get(hint.replace("-", "_").replace(" ", "_"))
        or _CATEGORY_ALIASES.get(hint.replace("_", " ").replace("-", " "))
    )

    candidate_strings = [hint]
    if alias_target and alias_target not in candidate_strings:
        candidate_strings.append(alias_target)

    hint_tokens = _tokenize(hint)
    categories = db.query(Category).all()

    best_category: Optional[Category] = None
    best_score = -1

    for category in categories:
        name = _clean(getattr(category, "name", None)) or ""
        slug = _clean(getattr(category, "slug", None)) or ""
        haystack = f"{name} {slug}".lower()
        score = -1

        for candidate in candidate_strings:
            if candidate == haystack:
                score = max(score, 100)
            elif candidate and candidate in haystack:
                score = max(score, 80)
            elif haystack and haystack in candidate:
                score = max(score, 60)

        category_tokens = set(_tokenize(haystack))
        overlap = len(set(hint_tokens) & category_tokens)
        if overlap > 0:
            score = max(score, overlap * 10)

        if score > best_score:
            best_score = score
            best_category = category

    if best_score <= 0:
        return None

    return best_category


def ingest_candidate_v2(
    *,
    db: Session,
    name: Any,
    lat: Any = None,
    lng: Any = None,
    address: Any = None,
    phone: Any = None,
    website: Any = None,
    source: Any = None,
    confidence: Any = None,
    category_hint: Any = None,
    category_id: Any = None,
    city_id: Any = None,
    city_slug: Any = None,
    city_name: Any = None,
    external_id: Any = None,
    raw_payload: Any = None,
) -> DiscoveryCandidate:
    clean_name = _normalize_name(name)
    if not clean_name:
        raise ValueError("name is required")

    clean_address = _clean(address)
    clean_phone = _clean(phone)
    clean_website = _clean(website)
    clean_source = _clean(source) or DEFAULT_SOURCE
    clean_category_hint = _clean(category_hint)
    clean_external_id = _clean(external_id)

    parsed_lat = _safe_float(lat)
    parsed_lng = _safe_float(lng)

    city = _resolve_city(
        db=db,
        city_id=city_id,
        city_slug=city_slug,
        city_name=city_name,
        address=clean_address,
        lat=parsed_lat,
        lng=parsed_lng,
    )

    if not city:
        raise ValueError(
            f"unable to resolve city for name={clean_name!r} address={clean_address!r}"
        )

    category = _resolve_category(
        db=db,
        category_id=category_id,
        category_hint=clean_category_hint,
    )

    candidate = upsert_discovery_candidate_v2(
        db=db,
        name=clean_name,
        city_id=city.id,
        external_id=clean_external_id,
        source=clean_source,
        category_id=category.id if category else None,
        lat=parsed_lat,
        lng=parsed_lng,
        address=clean_address,
        phone=clean_phone,
        website=clean_website,
        category_hint=clean_category_hint,
        confidence_score=_clamp_confidence(confidence),
        raw_payload=raw_payload if isinstance(raw_payload, dict) else None,
    )

    db.flush()

    logger.info(
        "discovery_candidate_upserted name=%s city=%s source=%s external_id=%s candidate_id=%s",
        clean_name,
        getattr(city, "slug", None) or getattr(city, "name", None),
        clean_source,
        clean_external_id,
        getattr(candidate, "id", None),
    )

    return candidate
