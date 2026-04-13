from __future__ import annotations

from typing import Optional


def _norm(value: Optional[str]) -> str:
    if not value:
        return "all"
    return value.strip().lower()


def _round_coord(v: float) -> float:
    return round(v, 4)


def feed_key(
    *,
    city_id: Optional[str],
    page_size: int,
    page: int = 1,
) -> str:

    city = _norm(city_id)

    return f"feed:{city}:{page}:{page_size}"


def map_key(
    *,
    lat: float,
    lng: float,
    radius_km: float,
    limit: int,
    city_id: Optional[str],
    category_id: Optional[str],
) -> str:

    city = _norm(city_id)
    cat = _norm(category_id)

    return (
        f"map:"
        f"{_round_coord(lat)}:"
        f"{_round_coord(lng)}:"
        f"{radius_km}:"
        f"{limit}:"
        f"{city}:"
        f"{cat}"
    )


def search_cache_key(
    *,
    query: str,
    city_id: str,
    category_id: Optional[str],
    price_tier: Optional[int],
    page: int,
    page_size: int,
) -> str:

    q = query.lower().strip()
    city = _norm(city_id)
    cat = _norm(category_id)
    price = price_tier if price_tier is not None else "all"

    return (
        f"search:"
        f"{q}:"
        f"{city}:"
        f"{cat}:"
        f"{price}:"
        f"{page}:"
        f"{page_size}"
    )


def place_detail_key(
    *,
    place_id: str,
) -> str:

    return f"place:{place_id}"


def categories_cache_key() -> str:
    return "categories:all"


def cities_cache_key() -> str:
    return "cities:all"