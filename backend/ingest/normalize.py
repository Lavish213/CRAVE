from typing import Any


def infer_category(p: dict) -> str:
    tags = p.get("tags", {}) or {}

    amenity = tags.get("amenity")
    shop = tags.get("shop")
    cuisine = tags.get("cuisine")

    if amenity in {"restaurant", "fast_food", "cafe", "bar"}:
        return amenity
    if amenity == "ice_cream":
        return "dessert"

    if shop == "bakery":
        return "bakery"
    if shop in {"supermarket", "convenience"}:
        return "grocery"

    if cuisine:
        return "restaurant"

    return "unknown"


def normalize(raw: Any) -> list[dict]:
    """
    FINAL LOCKED NORMALIZER

    Preserves:
    - id
    - name
    - lat/lng
    - category
    - external_url
    - description
    - operational defaults
    - raw payload
    """

    # OSM payload format
    if isinstance(raw, dict) and "elements" in raw:
        raw = raw["elements"]

    if not isinstance(raw, list):
        return []

    normalized: list[dict] = []

    for p in raw:
        if not isinstance(p, dict):
            continue

        # handle node vs way
        lat = p.get("lat")
        lon = p.get("lon") or p.get("lng")

        if lat is None or lon is None:
            center = p.get("center")
            if center:
                lat = center.get("lat")
                lon = center.get("lon")

        if lat is None or lon is None:
            continue

        tags = p.get("tags", {}) or {}
        name = tags.get("name")

        if not name or not isinstance(name, str):
            continue

        name = name.strip()
        if not name:
            continue

        try:
            normalized.append(
                {
                    "id": str(p.get("id")),
                    "name": name,
                    "lat": float(lat),
                    "lng": float(lon),
                    "category": infer_category(p),
                    "external_url": tags.get("website"),
                    "description": tags.get("description"),
                    "open_status": "unknown",
                    "confidence": "low",
                    "raw": p,
                }
            )
        except (TypeError, ValueError):
            continue

    return normalized