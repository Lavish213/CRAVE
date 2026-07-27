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


def place_menu_key(
    *,
    place_id: str,
) -> str:
    return f"menu:{place_id}"


def feed_city_prefix(
    *,
    city_id: str,
) -> str:
    """Prefix for all feed keys belonging to a city. Used for prefix invalidation."""
    return f"feed:{_norm(city_id)}:"


def provider_probe_negative_key(
    *,
    url: str,
) -> str:
    """
    Negative-result cache key for a probed URL.
    A hit means: this URL is confirmed blocked/dead — skip fetch.
    """
    import hashlib
    url_hash = hashlib.sha256((url or "").strip().encode()).hexdigest()[:20]
    return f"neg:probe:{url_hash}"


def blocked_domain_key(
    *,
    domain: str,
) -> str:
    """Negative-result cache key for a domain confirmed blocked/dead."""
    return f"neg:domain:{(domain or '').strip().lower()}"


def extraction_result_key(
    *,
    place_id: str,
) -> str:
    """
    Short-lived cache for successful extraction results.
    Prevents redundant re-extraction within the same batch window.
    """
    return f"extract:{place_id}"