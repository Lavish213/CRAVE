from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional


_CATEGORY_MAP = {
    "restaurant": "restaurant",
    "food service": "restaurant",
    "food establishment": "restaurant",
    "food facility": "restaurant",
    "eating establishment": "restaurant",
    "retail food": "restaurant",
    "food prep": "restaurant",
    "food vendor": "restaurant",
    "mobile food": "restaurant",
    "food truck": "restaurant",
    "catering": "restaurant",
    "bakery": "bakery",
    "cafe": "cafe",
    "coffee": "coffee",
    "deli": "american",
    "bar": "bar",
    "pub": "bar",
    "tavern": "bar",
    "night club": "bar",
    "liquor": "bar",
    "pizza": "pizza",
    "sushi": "japanese",
    "mexican": "mexican",
    "taqueria": "mexican",
    "chinese": "chinese",
    "thai": "thai",
    "indian": "indian",
    "italian": "italian",
    "seafood": "seafood",
    "ice cream": "desserts",
    "frozen dessert": "desserts",
    "dessert": "desserts",
    "donut": "desserts",
    "fast food": "fast casual",
    "fast casual": "fast casual",
    "buffet": "restaurant",
    "vegan": "vegan",
    "vegetarian": "vegan",
    "halal": "halal",
}

_NOISE = re.compile(r"\s+")


def _clean(value: Any) -> Optional[str]:
    if not value:
        return None
    s = str(value).strip()
    s = _NOISE.sub(" ", s)
    return s or None


def _normalize_address(address: Optional[str], city: Optional[str], state: Optional[str], zip_code: Optional[str]) -> Optional[str]:
    parts = [p for p in [address, city, state, zip_code] if p]
    return ", ".join(parts) if parts else None


def _derive_category_hint(raw_category: Optional[str], name: Optional[str]) -> Optional[str]:
    text = " ".join(filter(None, [raw_category, name])).lower()
    for keyword, hint in _CATEGORY_MAP.items():
        if keyword in text:
            return hint
    return "restaurant"


def _make_external_id(name: str, address: Optional[str]) -> str:
    key = f"{name.lower().strip()}:{(address or '').lower().strip()}"
    sha = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"health:{sha}"


def normalize_records(parsed: List[Dict]) -> List[Dict]:
    normalized = []

    for record in parsed:
        name = _clean(record.get("name"))
        if not name:
            continue

        address_line = _clean(record.get("address"))
        city = _clean(record.get("city"))
        state = _clean(record.get("state"))
        zip_code = _clean(record.get("zip"))

        full_address = _normalize_address(address_line, city, state, zip_code)

        external_id = _make_external_id(name, full_address)

        category_hint = _derive_category_hint(
            record.get("category_raw"),
            name,
        )

        normalized.append({
            "source": "health_dept",
            "external_id": external_id,
            "name": name,
            "address": full_address,
            "city": city,
            "state": state,
            "zip": zip_code,
            "lat": record.get("lat"),
            "lng": record.get("lng"),
            "category_hint": category_hint,
            "confidence": 0.75 if (record.get("lat") and record.get("lng")) else 0.5,
            "raw_payload": record.get("raw_payload") or {},
        })

    return normalized
