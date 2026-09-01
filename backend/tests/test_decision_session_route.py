"""
Coverage for GET /api/v1/decision-session -- confirms the route is wired
up, reuses the same candidate-retrieval Layer 1 as /places, and
serializes cards through the real PlaceOut schema without crashing.
The role-selection logic itself is covered independently and in more
detail by test_decision_session_builder.py (pure-function, no DB).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.category import Category
from app.db.models.place_video import PlaceVideo, STATUS_APPROVED, MOD_APPROVED

client = TestClient(app)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_category(db, name: str) -> Category:
    existing = db.query(Category).filter(Category.name == name).first()
    if existing:
        return existing
    cat = Category(slug=name.lower(), name=name)
    db.add(cat)
    db.commit()
    return cat


def test_decision_session_returns_cards_for_a_seeded_city(db):
    city_id = str(uuid.uuid4())
    db.add(City(id=city_id, name="Decision City", slug=f"decision-city-{city_id[:8]}",
                lat=37.0, lng=-122.0, is_active=True))
    db.commit()

    sushi = _make_category(db, "Sushi")
    tacos = _make_category(db, "Tacos")

    place_ids = []
    for i, (score, cat) in enumerate([(0.45, sushi), (0.40, tacos), (0.20, sushi)]):
        pid = str(uuid.uuid4())
        place_ids.append(pid)
        p = Place(
            id=pid, name=f"Place {i}", city_id=city_id,
            lat=37.0 + i * 0.001, lng=-122.0, is_active=True, rank_score=score,
        )
        p.categories.append(cat)
        db.add(p)
    db.commit()

    db.add(PlaceVideo(
        place_id=place_ids[0], uploaded_by=f"user-{uuid.uuid4().hex[:8]}",
        status=STATUS_APPROVED, moderation_status=MOD_APPROVED,
    ))
    db.commit()

    try:
        resp = client.get("/api/v1/decision-session", params={"city_id": city_id})
        assert resp.status_code == 200
        body = resp.json()
        assert "cards" in body and "degraded" in body

        cards = body["cards"]
        assert len(cards) <= 3
        seen_ids = set()
        for card in cards:
            assert card["role"] in ("best_fit", "safe_bet", "wildcard")
            assert isinstance(card["reason_codes"], list) and card["reason_codes"]
            assert card["place"]["id"] not in seen_ids
            seen_ids.add(card["place"]["id"])
        video_card = next(card for card in cards if card["place"]["id"] == place_ids[0])
        assert video_card["place"]["has_video"] is True
    finally:
        db.query(PlaceVideo).filter(PlaceVideo.place_id.in_(place_ids)).delete(
            synchronize_session=False
        )
        db.query(Place).filter(Place.id.in_(place_ids)).delete(synchronize_session=False)
        db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
        db.commit()


def test_decision_session_degrades_gracefully_with_no_candidates(db):
    empty_city_id = str(uuid.uuid4())
    db.add(City(id=empty_city_id, name="Empty City", slug=f"empty-city-{empty_city_id[:8]}",
                lat=0.0, lng=0.0, is_active=True))
    db.commit()

    try:
        resp = client.get("/api/v1/decision-session", params={"city_id": empty_city_id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["cards"] == []
        assert body["degraded"] is True
    finally:
        db.query(City).filter(City.id == empty_city_id).delete(synchronize_session=False)
        db.commit()
