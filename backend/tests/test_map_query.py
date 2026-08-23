"""
Coverage for app.services.query.map_query.fetch_places_for_map's primary
image resolution.

This was previously resolved via a correlated scalar subquery embedded
per-row directly in the main SELECT — an N+1-shaped cost (one extra
filtered-sort lookup against place_images for every one of up to `limit`
rows), unlike every other list surface in the app (feed, search), which
resolve it via a single separate bulk query
(get_primary_image_urls_bulk). Live-confirmed in production: a map
request timed out client-side at 25s while feed/search/detail all loaded
normally in the same session. Fixed by switching to the same bulk
pattern; these tests exist to lock in that the switch didn't change
*behavior*, only *shape* — same visibility filtering, same per-place
correctness, no cross-contamination between places in the same result.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_HIDDEN,
    VISIBILITY_SHOWCASE,
)
from app.services.query.map_query import fetch_places_for_map


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_city(db) -> City:
    city = City(
        id=str(uuid.uuid4()),
        name="Map Query Test City",
        slug=f"map-query-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    return city


def _make_place(db, city: City, *, name: str, lat: float, lng: float) -> Place:
    place = Place(name=name, city_id=city.id, lat=lat, lng=lng)
    db.add(place)
    db.commit()
    return place


def test_fetch_places_for_map_resolves_primary_image_url(db):
    city = _make_city(db)
    place = _make_place(db, city, name="Has Photo", lat=37.8, lng=-122.27)
    db.add(PlaceImage(
        place_id=place.id,
        url="https://example.com/photo.jpg",
        is_primary=True,
        visibility_status=VISIBILITY_SHOWCASE,
        confidence=0.9,
    ))
    db.commit()

    result = fetch_places_for_map(db, lat=37.8, lng=-122.27, radius_km=5.0)

    assert result["ok"] is True
    row = next(p for p in result["places"] if p["id"] == place.id)
    assert row["primary_image_url"] == "https://example.com/photo.jpg"


def test_fetch_places_for_map_excludes_hidden_primary_image(db):
    city = _make_city(db)
    place = _make_place(db, city, name="Hidden Photo Only", lat=37.8, lng=-122.27)
    db.add(PlaceImage(
        place_id=place.id,
        url="https://example.com/hidden.jpg",
        is_primary=True,
        visibility_status=VISIBILITY_HIDDEN,
        confidence=0.9,
    ))
    db.commit()

    result = fetch_places_for_map(db, lat=37.8, lng=-122.27, radius_km=5.0)

    row = next(p for p in result["places"] if p["id"] == place.id)
    assert row["primary_image_url"] is None


def test_fetch_places_for_map_does_not_cross_contaminate_images_between_places(db):
    # The exact failure mode a naive bulk-query rewrite could introduce:
    # picking the wrong place's image, or the highest-confidence image
    # across the whole batch instead of per-place.
    city = _make_city(db)
    place_a = _make_place(db, city, name="Place A", lat=37.80, lng=-122.27)
    place_b = _make_place(db, city, name="Place B", lat=37.801, lng=-122.271)

    db.add(PlaceImage(
        place_id=place_a.id, url="https://example.com/a.jpg",
        is_primary=True, visibility_status=VISIBILITY_SHOWCASE, confidence=0.5,
    ))
    db.add(PlaceImage(
        place_id=place_b.id, url="https://example.com/b.jpg",
        is_primary=True, visibility_status=VISIBILITY_SHOWCASE, confidence=0.95,
    ))
    db.commit()

    result = fetch_places_for_map(db, lat=37.8, lng=-122.27, radius_km=5.0)

    row_a = next(p for p in result["places"] if p["id"] == place_a.id)
    row_b = next(p for p in result["places"] if p["id"] == place_b.id)
    assert row_a["primary_image_url"] == "https://example.com/a.jpg"
    assert row_b["primary_image_url"] == "https://example.com/b.jpg"


def test_fetch_places_for_map_place_with_no_image_gets_none(db):
    city = _make_city(db)
    place = _make_place(db, city, name="No Photo", lat=37.8, lng=-122.27)

    result = fetch_places_for_map(db, lat=37.8, lng=-122.27, radius_km=5.0)

    row = next(p for p in result["places"] if p["id"] == place.id)
    assert row["primary_image_url"] is None
