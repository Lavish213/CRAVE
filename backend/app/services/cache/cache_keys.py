from __future__ import annotations

from typing import Optional


def _norm(value: Optional[str]) -> str:
    if not value:
        return "all"
    return value.strip().lower()


def _round_grid(v: Optional[float], decimals: int = 2) -> str:
    """
    Coarse-grid rounding for geo cache keys.

    A shared cache only pays off when different requests actually land on
    the same key -- rounding to 4 decimal places (~11m) meant two different
    users a block apart, or the same user panning slightly, would almost
    never share a cache entry, making the cache real but nearly useless in
    practice. 2 decimals (~1.1km at the equator) is coarse enough that
    "nearby" requests actually collide and share one cached computation,
    while still being far finer than any city/neighborhood-scale query.

    Returns "none" (a string, distinct from any numeric "0.00"-style
    value) when the coordinate wasn't supplied at all, so "no location
    given" never collides with a real rounded coordinate.
    """
    if v is None:
        return "none"
    return f"{round(v, decimals):.{decimals}f}"


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
        f"{_round_grid(lat)}:"
        f"{_round_grid(lng)}:"
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
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    page: int,
    page_size: int,
) -> str:

    q = query.lower().strip()
    city = _norm(city_id)
    cat = _norm(category_id)
    price = price_tier if price_tier is not None else "all"

    # lat/lng must be part of the key: when supplied, search_query.py makes
    # distance the *primary* sort key (and, combined with LIMIT/OFFSET,
    # this changes which rows page 1 even contains) -- without them here,
    # one caller's location-sorted results would get served straight back
    # to a completely different caller who happened to search the same
    # term within the TTL window. Grid-rounded (not raw) for the same
    # reason map_key is: a shared cache only helps if nearby requests
    # actually collide on the same key.
    loc = f"{_round_grid(lat)}:{_round_grid(lng)}"

    return (
        f"search:"
        f"{q}:"
        f"{city}:"
        f"{cat}:"
        f"{price}:"
        f"{loc}:"
        f"{page}:"
        f"{page_size}"
    )


def place_detail_key(
    *,
    place_id: str,
) -> str:

    return f"place:{place_id}"


def leaderboard_global_base_key(
    *,
    city_slug: Optional[str],
) -> str:
    """
    Cache key for the global leaderboard's *base* ranking -- deliberately
    keyed only on city, not on the caller, not on `limit`, and not on
    blocked users: the underlying ranked list is identical for every
    viewer. Per-viewer block-filtering is applied in Python after reading
    this cached (or freshly computed) pool, the same reason
    /place/{id}/friends is never folded into the shared place-detail
    cache -- baking a per-viewer filter into the cached value itself
    would either leak data across viewers or force disabling the cache.
    """
    return f"leaderboard:global:{_norm(city_slug)}"


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