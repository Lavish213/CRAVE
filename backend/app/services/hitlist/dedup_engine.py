# app/services/hitlist/dedup_engine.py
from __future__ import annotations
import hashlib
from typing import Optional


def _h(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _norm(name: str) -> str:
    return " ".join((name or "").lower().strip().split())


def compute_dedup_key(
    *,
    place_id: Optional[str] = None,
    source_url: Optional[str] = None,
    place_name: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    city: Optional[str] = None,
) -> str:
    if place_id:
        return f"place:{place_id}"
    if source_url:
        return f"url:{_h(source_url.lower().strip())}"
    if place_name and lat is not None and lng is not None:
        return f"geo:{_h(f'{_norm(place_name)}:{round(lat,3)}:{round(lng,3)}')}"
    if place_name and city:
        return f"city:{_h(f'{_norm(place_name)}:{_norm(city)}')}"
    if place_name:
        return f"name:{_h(_norm(place_name))}"
    raise ValueError("Cannot compute dedup key: insufficient data provided")
