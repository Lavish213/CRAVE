"""
Coverage for POST /recommendations/events -- the Recommendation Ledger's
ingest endpoint.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id_optional
from app.db.session import SessionLocal
from app.db.models.recommendation_event import RecommendationEvent

client = TestClient(app)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(get_current_user_id_optional, None)
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _cleanup(db, event_ids):
    if event_ids:
        db.query(RecommendationEvent).filter(
            RecommendationEvent.id.in_(event_ids)
        ).delete(synchronize_session=False)
        db.commit()


def test_anonymous_batch_is_accepted(db):
    app.dependency_overrides[get_current_user_id_optional] = lambda: None
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"

    resp = client.post(
        "/api/v1/recommendations/events",
        json={
            "events": [
                {"surface": "feed", "event_type": "impression", "position": 0, "session_id": session_id},
                {"surface": "feed", "event_type": "click", "position": 0, "session_id": session_id},
            ]
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"accepted": 2}

    rows = db.query(RecommendationEvent).filter(
        RecommendationEvent.session_id == session_id
    ).all()
    try:
        assert len(rows) == 2
        assert all(r.user_id is None for r in rows)
    finally:
        _cleanup(db, [r.id for r in rows])


def test_signed_in_batch_records_user_id(db):
    app.dependency_overrides[get_current_user_id_optional] = lambda: "user-ledger-test"
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"

    resp = client.post(
        "/api/v1/recommendations/events",
        json={"events": [{"surface": "search", "event_type": "impression", "query": "pizza", "session_id": session_id}]},
    )

    assert resp.status_code == 200
    assert resp.json() == {"accepted": 1}

    rows = db.query(RecommendationEvent).filter(
        RecommendationEvent.session_id == session_id
    ).all()
    try:
        assert len(rows) == 1
        assert rows[0].user_id == "user-ledger-test"
        assert rows[0].query == "pizza"
    finally:
        _cleanup(db, [r.id for r in rows])


def test_invalid_events_are_dropped_but_batch_still_succeeds(db):
    app.dependency_overrides[get_current_user_id_optional] = lambda: None
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"

    resp = client.post(
        "/api/v1/recommendations/events",
        json={
            "events": [
                {"surface": "not_real", "event_type": "impression", "session_id": session_id},
                {"surface": "feed", "event_type": "impression", "session_id": session_id},
            ]
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"accepted": 1}

    rows = db.query(RecommendationEvent).filter(
        RecommendationEvent.session_id == session_id
    ).all()
    try:
        assert len(rows) == 1
    finally:
        _cleanup(db, [r.id for r in rows])


def test_empty_batch_is_accepted_as_a_no_op():
    app.dependency_overrides[get_current_user_id_optional] = lambda: None
    resp = client.post("/api/v1/recommendations/events", json={"events": []})
    assert resp.status_code == 200
    assert resp.json() == {"accepted": 0}


def test_oversized_batch_is_rejected():
    app.dependency_overrides[get_current_user_id_optional] = lambda: None
    events = [{"surface": "feed", "event_type": "impression"} for _ in range(201)]
    resp = client.post("/api/v1/recommendations/events", json={"events": events})
    assert resp.status_code == 400
