"""
Coverage for Wave 7's backend groundwork (Place Detail relationship
hierarchy): reason_role/reason_source persistence on save-creation,
visit_confirmation_count (a real, not fabricated, repeat-visit signal),
visit_evidence_for_place()'s single-place lookup, and the new
GET /place/{id}/relationship endpoint. See
docs/CLAUDE_EXECUTION_BRIEF_WAVES_7_10_2026-09-08.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.hitlist_save import HitlistSave
from app.db.models.visit_evidence import VisitEvidence, VISIT_TIER_VERIFIED
from app.services.visit_evidence_service import visit_evidence_for_place

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


@pytest.fixture
def city_and_place(db):
    city_id = str(uuid.uuid4())
    db.add(City(
        id=city_id, name="Wave7 Test City",
        slug=f"wave7-test-city-{city_id[:8]}",
        lat=37.0, lng=-122.0, is_active=True,
    ))
    place = Place(
        id=str(uuid.uuid4()), name="Wave7 Test Place", city_id=city_id,
        lat=37.0, lng=-122.0, is_active=True, rank_score=0.5,
    )
    db.add(place)
    db.commit()
    yield city_id, place
    db.query(VisitEvidence).filter(VisitEvidence.place_id == place.id).delete(
        synchronize_session=False
    )
    db.query(HitlistSave).filter(HitlistSave.place_id == place.id).delete(
        synchronize_session=False
    )
    db.query(Place).filter(Place.id == place.id).delete(synchronize_session=False)
    db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
    db.commit()


def test_save_persists_reason_role_and_source(city_and_place, db):
    _city_id, place = city_and_place
    _as_user(f"user-{uuid.uuid4().hex[:8]}")

    resp = client.post(
        "/api/v1/saves",
        json={"place_id": place.id, "reason_role": "best_fit", "reason_source": "craves"},
    )
    assert resp.status_code == 201

    listed = client.get("/api/v1/saves").json()["items"][0]
    assert listed["reason_role"] == "best_fit"
    assert listed["reason_source"] == "craves"
    assert listed["visit_confirmation_count"] == 0


def test_save_without_reason_is_still_a_normal_valid_save(city_and_place, db):
    _city_id, place = city_and_place
    _as_user(f"user-{uuid.uuid4().hex[:8]}")

    resp = client.post("/api/v1/saves", json={"place_id": place.id})
    assert resp.status_code == 201

    listed = client.get("/api/v1/saves").json()["items"][0]
    assert listed["reason_role"] is None
    assert listed["reason_source"] is None


def test_visit_confirmation_count_increments_only_on_false_to_true_transition(city_and_place, db):
    _city_id, place = city_and_place
    _as_user(f"user-{uuid.uuid4().hex[:8]}")
    client.post("/api/v1/saves", json={"place_id": place.id})

    # First confirmation: False -> True.
    resp = client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})
    assert resp.status_code == 200
    assert client.get("/api/v1/saves").json()["items"][0]["visit_confirmation_count"] == 1

    # Redundant re-send of visited=true (e.g. a notes-only edit that also
    # resends the current value) must not double-count.
    client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True, "notes": "still good"})
    assert client.get("/api/v1/saves").json()["items"][0]["visit_confirmation_count"] == 1

    # Un-mark, then re-confirm: a genuine second visit.
    client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": False})
    client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})
    assert client.get("/api/v1/saves").json()["items"][0]["visit_confirmation_count"] == 2


def test_visit_evidence_for_place_returns_none_when_no_evidence_exists(city_and_place, db):
    _city_id, place = city_and_place
    result = visit_evidence_for_place(db, user_id=f"user-{uuid.uuid4().hex[:8]}", place_id=place.id)
    assert result is None


def test_visit_evidence_for_place_returns_the_most_recent_record(city_and_place, db):
    _city_id, place = city_and_place
    user_id = f"user-{uuid.uuid4().hex[:8]}"

    db.add(VisitEvidence(
        id=str(uuid.uuid4()), user_id=user_id, place_id=place.id,
        tier=VISIT_TIER_VERIFIED, source="test_source_a", source_ref="ref-a",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ))
    db.add(VisitEvidence(
        id=str(uuid.uuid4()), user_id=user_id, place_id=place.id,
        tier=VISIT_TIER_VERIFIED, source="test_source_b", source_ref="ref-b",
        occurred_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    ))
    db.commit()

    result = visit_evidence_for_place(db, user_id=user_id, place_id=place.id)
    assert result is not None
    assert result.source == "test_source_b"


def test_place_relationship_endpoint_reports_never_saved(city_and_place, db):
    _city_id, place = city_and_place
    _as_user(f"user-{uuid.uuid4().hex[:8]}")

    resp = client.get(f"/api/v1/place/{place.id}/relationship")
    assert resp.status_code == 200
    body = resp.json()
    assert body["saved"] is False
    assert body["visited"] is False
    assert body["visit_evidence_tier"] is None


def test_place_relationship_endpoint_reports_saved_and_visited_state(city_and_place, db):
    _city_id, place = city_and_place
    _as_user(f"user-{uuid.uuid4().hex[:8]}")
    client.post(
        "/api/v1/saves",
        json={"place_id": place.id, "reason_role": "safe_bet", "reason_source": "decision_session"},
    )
    client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})

    resp = client.get(f"/api/v1/place/{place.id}/relationship")
    assert resp.status_code == 200
    body = resp.json()
    assert body["saved"] is True
    assert body["visited"] is True
    assert body["reason_role"] == "safe_bet"
    assert body["reason_source"] == "decision_session"
    assert body["visit_confirmation_count"] == 1
    assert body["visit_evidence_tier"] == "declared"


def test_place_relationship_endpoint_is_scoped_to_the_calling_user(city_and_place, db):
    """IDOR guard, same discipline as the memory PATCH endpoint."""
    _city_id, place = city_and_place
    owner = f"user-{uuid.uuid4().hex[:8]}"
    intruder = f"user-{uuid.uuid4().hex[:8]}"

    _as_user(owner)
    client.post("/api/v1/saves", json={"place_id": place.id})
    client.patch(f"/api/v1/saves/{place.id}/memory", json={"visited": True})

    _as_user(intruder)
    resp = client.get(f"/api/v1/place/{place.id}/relationship")
    assert resp.status_code == 200
    body = resp.json()
    assert body["saved"] is False
    assert body["visited"] is False
