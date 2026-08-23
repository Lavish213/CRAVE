"""
Coverage for app/services/cache/cache_keys.py.

Two real things are being guarded here, both found in a live cache audit:

1. search_cache_key() previously omitted lat/lng entirely, even though
   search_query.py makes distance the *primary* sort key whenever they're
   supplied -- meaning one caller's location-sorted results could be
   served straight back to a completely different caller who searched the
   same term within the cache TTL. lat/lng must now be part of the key.

2. map_key() (and now search_cache_key()) round coordinates to a coarse
   grid (~1.1km) rather than the previous ~11m precision -- a shared
   cache only pays off when different requests actually land on the same
   key, and two nearby-but-not-identical requests almost never matched at
   11m precision.
"""
from __future__ import annotations

from app.services.cache.cache_keys import map_key, search_cache_key


def test_search_cache_key_differs_for_different_locations():
    key_sf = search_cache_key(
        query="pizza", city_id=None, category_id=None, price_tier=None,
        lat=37.7749, lng=-122.4194, page=1, page_size=20,
    )
    key_oakland = search_cache_key(
        query="pizza", city_id=None, category_id=None, price_tier=None,
        lat=37.8044, lng=-122.2712, page=1, page_size=20,
    )
    assert key_sf != key_oakland


def test_search_cache_key_differs_between_no_location_and_a_location():
    key_no_location = search_cache_key(
        query="pizza", city_id=None, category_id=None, price_tier=None,
        page=1, page_size=20,
    )
    key_with_location = search_cache_key(
        query="pizza", city_id=None, category_id=None, price_tier=None,
        lat=37.7749, lng=-122.4194, page=1, page_size=20,
    )
    assert key_no_location != key_with_location


def test_search_cache_key_same_grid_cell_collides_on_purpose():
    # Two points a short walk apart, both comfortably inside the same
    # ~1.1km grid cell (not straddling a rounding boundary), are meant to
    # share a cache entry. That's the whole point of grid-rounding: nearby
    # requests actually reuse the same computation instead of each
    # computing (and caching) their own.
    key_a = search_cache_key(
        query="ramen", city_id=None, category_id=None, price_tier=None,
        lat=37.7712, lng=-122.4192, page=1, page_size=20,
    )
    key_b = search_cache_key(
        query="ramen", city_id=None, category_id=None, price_tier=None,
        lat=37.7719, lng=-122.4186, page=1, page_size=20,
    )
    assert key_a == key_b


def test_search_cache_key_different_grid_cell_does_not_collide():
    key_sf = search_cache_key(
        query="ramen", city_id=None, category_id=None, price_tier=None,
        lat=37.7749, lng=-122.4194, page=1, page_size=20,
    )
    key_oakland = search_cache_key(
        query="ramen", city_id=None, category_id=None, price_tier=None,
        lat=37.8044, lng=-122.2712, page=1, page_size=20,
    )
    assert key_sf != key_oakland


def test_map_key_nearby_points_share_a_grid_cell():
    key_a = map_key(
        lat=37.7712, lng=-122.4192, radius_km=5, limit=250,
        city_id=None, category_id=None,
    )
    key_b = map_key(
        lat=37.7719, lng=-122.4186, radius_km=5, limit=250,
        city_id=None, category_id=None,
    )
    assert key_a == key_b


def test_map_key_distant_points_do_not_collide():
    key_sf = map_key(
        lat=37.7749, lng=-122.4194, radius_km=5, limit=250,
        city_id=None, category_id=None,
    )
    key_oakland = map_key(
        lat=37.8044, lng=-122.2712, radius_km=5, limit=250,
        city_id=None, category_id=None,
    )
    assert key_sf != key_oakland
