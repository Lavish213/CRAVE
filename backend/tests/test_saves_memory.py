"""
Coverage for the E2 Hitlist memory fields (visited/visited_at/notes) on
HitlistSave, and the PATCH /saves/{place_id}/memory endpoint that sets
them. See docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md.

Confirms:
  - GET /saves returns visited/visited_at/notes per item (default
    unvisited/no notes for a fresh save).
  - PATCH .../memory sets visited=true and stamps visited_at.
  - Un-marking visited (visited=false) clears visited_at, not leaves it
    stale.
  - notes can be set and explicitly cleared (sent as null) independently
    of visited.
  - A memory PATCH for a save that doesn't exist (wrong user or never
    saved) 404s, same IDOR-safe lookup as DELETE /saves/{place_id}.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.hitlist_save import HitlistSave
from app.db.models.place_video import PlaceVideo, STATUS_APPROVED, MOD_APPROVED

client = TestClient(app)


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _save_place(db, place: Place, user_id: str):
    _as_user(user_id)
    resp = client.post("/api/v1/saves", json={"place_id": place.id})
    assert resp.status_code == 201
    return resp


@pytest.fixture
def city_and_place(db):
    city_id = str(uuid.uuid4())
    db.add(City(
        id=city_id, name="Memory Test City",
        slug=f"memory-test-city-{city_id[:8]}",
        lat=37.0, lng=-122.0, is_active=True,
    ))
    place = Place(
        id=str(uuid.uuid4()), name="Memory Test Place", city_id=city_id,
        lat=37.0, lng=-122.0, is_active=True, rank_score=0.5,
    )
    db.add(place)
    db.commit()
    yield city_id, place
    db.query(PlaceVideo).filter(PlaceVideo.place_id == place.id).delete(
        synchronize_session=False
    )
    db.query(HitlistSave).filter(HitlistSave.place_id == place.id).delete(
        synchronize_session=False
    )
    db.query(Place).filter(Place.id == place.id).delete(synchronize_session=False)
    db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
    db.commit()


def test_get_saves_defaults_to_unvisited_with_no_notes(city_and_place, db):
    _city_id, place = city_and_place
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    _save_place(db, place, user_id)

    resp = client.get("/api/v1/saves")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["visited"] is False
    assert items[0]["visited_at"] is None
    assert items[0]["notes"] is None


def test_get_saves_reports_only_approved_visible_video(city_and_place, db):
    _city_id, place = city_and_place
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    _save_place(db, place, user_id)
    db.add(PlaceVideo(
        place_id=place.id, uploaded_by=user_id,
        status=STATUS_APPROVED, moderation_status=MOD_APPROVED,
    ))
    db.commit()

    item = client.get("/api/v1/saves").json()["items"][0]
    assert item["has_video"] is True


def test_marking_visited_sets_visited_at(city_and_place, db):
    _city_id, place = city_and_place
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    _save_place(db, place, user_id)

    resp = client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["visited"] is True
    assert body["visited_at"] is not None

    listed = client.get("/api/v1/saves").json()["items"][0]
    assert listed["visited"] is True
    assert listed["visited_at"] is not None


def test_unmarking_visited_clears_visited_at(city_and_place, db):
    _city_id, place = city_and_place
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    _save_place(db, place, user_id)

    client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})
    resp = client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["visited"] is False
    assert body["visited_at"] is None


def test_notes_set_and_explicitly_cleared(city_and_place, db):
    _city_id, place = city_and_place
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    _save_place(db, place, user_id)

    resp = client.patch(
        f"/api/v1/saves/{place.id}/memory", json={"notes": "great patio"}
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "great patio"

    listed = client.get("/api/v1/saves").json()["items"][0]
    assert listed["notes"] == "great patio"

    # Explicit null clears it (distinct from omitting the field, which
    # must leave it untouched -- covered below).
    resp = client.patch(f"/api/v1/saves/{place.id}/memory", json={"notes": None})
    assert resp.status_code == 200
    assert resp.json()["notes"] is None


def test_omitting_a_field_leaves_it_untouched(city_and_place, db):
    _city_id, place = city_and_place
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    _save_place(db, place, user_id)

    client.patch(f"/api/v1/saves/{place.id}/memory", json={"notes": "keep me"})
    resp = client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "keep me"
    assert resp.json()["visited"] is True


def test_memory_patch_404s_for_a_save_that_does_not_exist(city_and_place, db):
    _city_id, place = city_and_place
    _as_user(f"user-{uuid.uuid4().hex[:8]}")
    resp = client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})
    assert resp.status_code == 404


def test_memory_patch_is_scoped_to_the_owning_user(city_and_place, db):
    """IDOR guard: a different user's PATCH against the same place_id
    must not see or mutate the first user's save."""
    _city_id, place = city_and_place
    owner = f"user-{uuid.uuid4().hex[:8]}"
    intruder = f"user-{uuid.uuid4().hex[:8]}"
    _save_place(db, place, owner)

    _as_user(intruder)
    resp = client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})
    assert resp.status_code == 404

    _as_user(owner)
    listed = client.get("/api/v1/saves").json()["items"][0]
    assert listed["visited"] is False
