from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_NAME_KEYS = [
    "business_name", "facility_name", "name", "dba_name", "dba", "restaurant_name",
    "establishment_name", "owner_name", "permit_holder", "licensee_name",
]

_ADDRESS_KEYS = [
    "address", "facility_address", "street_address", "business_address",
    "location_address", "address_line1", "street", "addr",
]

_CITY_KEYS = [
    "city", "facility_city", "business_city", "city_name",
]

_STATE_KEYS = [
    "state", "facility_state", "business_state", "state_code",
]

_ZIP_KEYS = [
    "zip", "zip_code", "postal_code", "zipcode", "facility_zip", "business_zip",
]

_LAT_KEYS = [
    "latitude", "lat", "y", "geo_lat", "location_lat",
]

_LNG_KEYS = [
    "longitude", "lng", "lon", "x", "geo_lon", "geo_lng", "location_lon", "location_lng",
]

_CATEGORY_KEYS = [
    "business_type", "facility_type", "license_type", "permit_type",
    "establishment_type", "category", "type", "risk_category",
]

_FOOD_KEYWORDS = frozenset({
    "restaurant", "food", "cafe", "bakery", "deli", "pizza", "sushi", "bar",
    "pub", "grill", "bistro", "diner", "eatery", "kitchen", "buffet", "catering",
    "food service", "food establishment", "food facility", "food prep",
    "retail food", "food vendor", "mobile food",
})


def _pick(row: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for k in keys:
        v = row.get(k)
        if v is not None:
            s = str(v).strip()
            if s and s.lower() not in ("none", "null", "n/a", "na", "-", ""):
                return s
    lowered = {k.lower(): v for k, v in row.items()}
    for k in keys:
        v = lowered.get(k.lower())
        if v is not None:
            s = str(v).strip()
            if s and s.lower() not in ("none", "null", "n/a", "na", "-", ""):
                return s
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(str(value).strip())
        return f if f != 0.0 else None
    except Exception:
        return None


def _is_food_related(category: Optional[str], name: Optional[str]) -> bool:
    text = " ".join(filter(None, [category, name])).lower()
    return any(kw in text for kw in _FOOD_KEYWORDS)


def _extract_lat_lng(row: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    lat = _safe_float(_pick(row, _LAT_KEYS))
    lng = _safe_float(_pick(row, _LNG_KEYS))

    if lat is None or lng is None:
        loc = row.get("location") or row.get("geolocation") or row.get("geo")
        if isinstance(loc, dict):
            lat = lat or _safe_float(loc.get("latitude") or loc.get("lat"))
            lng = lng or _safe_float(loc.get("longitude") or loc.get("lon") or loc.get("lng"))
        elif isinstance(loc, str):
            match = re.search(r"\(?([-\d.]+)[,\s]+([-\d.]+)\)?", loc)
            if match:
                lat = lat or _safe_float(match.group(1))
                lng = lng or _safe_float(match.group(2))

    if lat is not None and lng is not None:
        if abs(lat) > 90 or abs(lng) > 180:
            return None, None
        if abs(lat) < 0.001 and abs(lng) < 0.001:
            return None, None

    return lat, lng


def parse_records(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    parsed = []

    for row in raw_rows:
        name = _pick(row, _NAME_KEYS)
        if not name:
            continue

        address = _pick(row, _ADDRESS_KEYS)
        city = _pick(row, _CITY_KEYS)
        state = _pick(row, _STATE_KEYS)
        zip_code = _pick(row, _ZIP_KEYS)
        category = _pick(row, _CATEGORY_KEYS)

        if not _is_food_related(category, name):
            continue

        lat, lng = _extract_lat_lng(row)

        parsed.append({
            "name": name,
            "address": address,
            "city": city,
            "state": state,
            "zip": zip_code,
            "lat": lat,
            "lng": lng,
            "category_raw": category,
            "raw_payload": row,
        })

    return parsed
