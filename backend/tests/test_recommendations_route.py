"""
Route-level coverage for GET /recommendations -- specifically has_video
wiring, which was added (PR #109) without a dedicated end-to-end test
through this route (gap flagged during independent review of that PR).
The underlying PlaceOut/_inject_category mechanism proving an ORM
attribute set before validation actually survives serialization is
already covered in test_place_video_presence.py; this proves the route
itself calls get_has_video_bulk and wires the result through.

A fresh test user has no PlaceRanking rows, so
get_recommendations() -> _find_similar_users() short-circuits on an
empty ranking vector and falls through to the cold-start path (any
active place, ordered by rank_score) -- no seeded ranking history
needed to exercise this.
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


def test_recommendations_reports_approved_visible_video(db):
    city_id = str(uuid.uuid4())
    place_id = str(uuid.uuid4())
    db.add(City(
        id=city_id, name="Recommendations Video Test City",
        slug=f"recs-video-test-{city_id[:8]}",
        lat=37.0, lng=-122.0, is_active=True,
    ))
    db.add(Place(
        id=place_id, name="Recommendations Video Test Place", city_id=city_id,
        lat=37.0, lng=-122.0, is_active=True, rank_score=0.5,
    ))
    db.commit()
    db.add(PlaceVideo(
        place_id=place_id, uploaded_by=f"user-{uuid.uuid4().hex[:8]}",
        status=STATUS_APPROVED, moderation_status=MOD_APPROVED,
    ))
    db.commit()

    try:
        _as_user(f"user-{uuid.uuid4().hex[:8]}")
        resp = client.get("/api/v1/recommendations")
        assert resp.status_code == 200
        items = resp.json()["items"]
        matching = [i for i in items if i["id"] == place_id]
        assert len(matching) == 1
        assert matching[0]["has_video"] is True
    finally:
        db.query(PlaceVideo).filter(PlaceVideo.place_id == place_id).delete(
            synchronize_session=False
        )
        db.query(Place).filter(Place.id == place_id).delete(synchronize_session=False)
        db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
        db.commit()


def test_recommendations_defaults_has_video_false_when_none_exists(db):
    city_id = str(uuid.uuid4())
    place_id = str(uuid.uuid4())
    db.add(City(
        id=city_id, name="Recommendations No-Video Test City",
        slug=f"recs-novideo-test-{city_id[:8]}",
        lat=37.0, lng=-122.0, is_active=True,
    ))
    db.add(Place(
        id=place_id, name="Recommendations No-Video Test Place", city_id=city_id,
        lat=37.0, lng=-122.0, is_active=True, rank_score=0.5,
    ))
    db.commit()

    try:
        _as_user(f"user-{uuid.uuid4().hex[:8]}")
        resp = client.get("/api/v1/recommendations")
        assert resp.status_code == 200
        items = resp.json()["items"]
        matching = [i for i in items if i["id"] == place_id]
        assert len(matching) == 1
        assert matching[0]["has_video"] is False
    finally:
        db.query(Place).filter(Place.id == place_id).delete(synchronize_session=False)
        db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
        db.commit()
