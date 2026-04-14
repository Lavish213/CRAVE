from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from app.services.cache.response_cache import response_cache

T = TypeVar("T")


def get_or_set(
    key: str,
    factory: Callable[[], T],
    ttl_seconds: int = 60,
) -> T:
    """
    Return cached value if present; else call factory(), cache result, and return it.

    Usage:
        result = get_or_set("my_key", lambda: expensive_query(), ttl_seconds=120)
    """
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    value = factory()
    response_cache.set(key, value, ttl_seconds=ttl_seconds)
    return value


def invalidate(key: str) -> None:
    """Delete a single cache entry by key."""
    response_cache.delete(key)


def invalidate_place(place_id: str) -> None:
    """Invalidate the place detail cache entry for a given place."""
    from app.services.cache.cache_keys import place_detail_key
    response_cache.delete(place_detail_key(place_id=place_id))


def invalidate_search(
    *,
    query: str,
    city_id: str,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> None:
    """Invalidate a specific search cache entry."""
    from app.services.cache.cache_keys import search_cache_key
    key = search_cache_key(
        query=query,
        city_id=city_id,
        category_id=category_id,
        price_tier=price_tier,
        page=page,
        page_size=page_size,
    )
    response_cache.delete(key)


def invalidate_feed(
    *,
    city_id: Optional[str],
    page: int = 1,
    page_size: int = 20,
) -> None:
    """Invalidate the feed cache entry for a city+page combination."""
    from app.services.cache.cache_keys import feed_key
    key = feed_key(city_id=city_id, page=page, page_size=page_size)
    response_cache.delete(key)
