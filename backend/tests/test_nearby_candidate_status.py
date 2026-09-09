# tests/test_nearby_candidate_status.py
#
# GET /nearby/candidate/{id}/status -- the missing piece a client needs after
# POST /nearby/confirm, which only ever returns a candidate_id (never a
# place_id, since confirming just creates a DiscoveryCandidate for the normal
# async promotion pipeline -- see nearby.py's own module docstring). Without
# this, a client has no way to find out later whether that candidate has
# since been promoted to a real Place.
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
from app.db.models.discovery_candidate import DiscoveryCandidate

client = TestClient(app)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    app.dependency_overrides[get_current_user_id] = lambda: "candidate-status-fixture-user"
    yield
    app.dependency_overrides.pop(rate_limit, None)
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def city(db):
    suffix = uuid.uuid4().hex[:8]
    c = City(slug=f"candstatus-{suffix}", name=f"Candidate Status City {suffix}")
    db.add(c)
    db.commit()

    yield c

    db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == c.id).delete()
    db.query(Place).filter(Place.city_id == c.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_candidate(db, city, **overrides) -> DiscoveryCandidate:
    suffix = uuid.uuid4().hex[:8]
    candidate = DiscoveryCandidate(
        name=f"Candidate {suffix}",
        city_id=city.id,
        source="user_gps",
        **overrides,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def test_unresolved_candidate_reports_not_resolved(db, city):
    candidate = _make_candidate(db, city)

    resp = client.get(f"/api/v1/nearby/candidate/{candidate.id}/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "candidate_id": candidate.id,
        "resolved": False,
        "place_id": None,
        "blocked": False,
    }


def test_resolved_candidate_reports_the_promoted_place_id(db, city):
    place = Place(name="Promoted Place", city_id=city.id, lat=37.77, lng=-122.42)
    db.add(place)
    db.flush()

    candidate = _make_candidate(db, city, resolved=True, resolved_place_id=place.id)

    resp = client.get(f"/api/v1/nearby/candidate/{candidate.id}/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved"] is True
    assert body["place_id"] == place.id

    db.query(Place).filter(Place.id == place.id).delete()
    db.commit()


def test_blocked_candidate_reports_blocked_without_a_place_id(db, city):
    candidate = _make_candidate(db, city, blocked=True)

    resp = client.get(f"/api/v1/nearby/candidate/{candidate.id}/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["blocked"] is True
    assert body["resolved"] is False
    assert body["place_id"] is None


def test_unknown_candidate_id_returns_404():
    resp = client.get(f"/api/v1/nearby/candidate/{uuid.uuid4()}/status")

    assert resp.status_code == 404
