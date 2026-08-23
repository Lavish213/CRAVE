"""
Coverage for get_saved_places_geojson — the "my places" Map tab layer,
the personal-curated-map feature both Beli and Biter advertise that
CRAVE's Map tab never had (it only ever showed the global catalog).
Reuses the existing saves data (HitlistSave, dedup_key convention from
app/api/v1/routes/saves.py) rather than a new table.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.hitlist_save import HitlistSave
from app.services.query.saved_places_map_query import get_saved_places_geojson


@pytest.fixture
def db():
    created = {"place_ids": [], "city_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["place_ids"]:
            session.query(HitlistSave).filter(
                HitlistSave.place_id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
            session.query(Place).filter(
                Place.id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
        if created["city_ids"]:
            session.query(City).filter(
                City.id.in_(created["city_ids"])
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def _make_place(session, created, *, name: str, lat: float, lng: float) -> Place:
    city = City(
        id=str(uuid.uuid4()), name="Saved Places Map Test City",
        slug=f"saved-places-map-test-{uuid.uuid4().hex[:8]}",
        lat=lat, lng=lng, is_active=True,
    )
    session.add(city)
    session.commit()
    created["city_ids"].append(city.id)
    place = Place(name=name, city_id=city.id, lat=lat, lng=lng)
    session.add(place)
    session.commit()
    created["place_ids"].append(place.id)
    return place


def _save(session, *, user_id: str, place: Place) -> None:
    session.add(HitlistSave(
        user_id=user_id,
        place_name=place.name,
        place_id=place.id,
        resolution_status="resolved",
        dedup_key=f"save:{user_id}:{place.id}",
    ))
    session.commit()


def test_returns_geojson_features_for_saved_places(db):
    session, created = db
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    place = _make_place(session, created, name="Saved Spot", lat=37.8, lng=-122.27)
    _save(session, user_id=user_id, place=place)

    result = get_saved_places_geojson(session, user_id=user_id)

    assert result["type"] == "FeatureCollection"
    ids = [f["properties"]["id"] for f in result["features"]]
    assert place.id in ids
    feature = next(f for f in result["features"] if f["properties"]["id"] == place.id)
    assert feature["geometry"]["coordinates"] == [place.lng, place.lat]
    assert feature["properties"]["tier"] == "default"


def test_excludes_other_users_saves(db):
    session, created = db
    place = _make_place(session, created, name="Someone Else's Save", lat=37.8, lng=-122.27)
    _save(session, user_id=f"other-{uuid.uuid4().hex[:8]}", place=place)

    result = get_saved_places_geojson(session, user_id=f"me-{uuid.uuid4().hex[:8]}")

    assert result["features"] == []


def test_returns_empty_when_no_saves(db):
    session, _created = db
    result = get_saved_places_geojson(session, user_id=f"user-{uuid.uuid4().hex[:8]}")
    assert result == {"type": "FeatureCollection", "features": []}


def test_excludes_hitlist_entries_that_are_not_place_backed_saves(db):
    # A raw (pre-resolution) hitlist entry with no place_id, and a
    # craves-flow dedup_key (not the "save:" prefix) must never leak in.
    session, created = db
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    session.add(HitlistSave(
        user_id=user_id, place_name="Unresolved Wishlist Item",
        place_id=None, resolution_status="raw", dedup_key="raw:some-hash",
    ))
    session.commit()

    result = get_saved_places_geojson(session, user_id=user_id)

    assert result["features"] == []
