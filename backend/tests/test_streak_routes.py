"""
Coverage for app/api/v1/routes/streak.py -- the thin HTTP wrapper around
streak_service. Business-logic edge cases (day-boundary math, timezone
fallback) are covered in test_streak_service.py; this just checks the
route wiring: GET never has a side effect, POST does, and the response
shape is what the frontend expects.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.user_streak import UserStreak

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
def cleanup():
    user_ids = []
    yield user_ids
    session = SessionLocal()
    try:
        if user_ids:
            session.query(UserStreak).filter(
                UserStreak.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            session.commit()
    finally:
        session.close()


def test_get_me_with_no_history_returns_zeros(cleanup):
    user_id = f"streak_route_{uuid.uuid4().hex[:8]}"
    cleanup.append(user_id)
    _as_user(user_id)

    resp = client.get("/api/v1/streak/me")

    assert resp.status_code == 200
    assert resp.json() == {"current_streak": 0, "longest_streak": 0, "last_active_date": None}


def test_get_me_never_records_activity_as_a_side_effect(cleanup):
    user_id = f"streak_route_{uuid.uuid4().hex[:8]}"
    cleanup.append(user_id)
    _as_user(user_id)

    client.get("/api/v1/streak/me")
    client.get("/api/v1/streak/me")

    session = SessionLocal()
    try:
        row = session.query(UserStreak).filter(UserStreak.user_id == user_id).one_or_none()
        assert row is None
    finally:
        session.close()


def test_ping_records_activity_and_returns_streak_of_one(cleanup):
    user_id = f"streak_route_{uuid.uuid4().hex[:8]}"
    cleanup.append(user_id)
    _as_user(user_id)

    resp = client.post("/api/v1/streak/ping", json={"timezone": "America/Los_Angeles"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_streak"] == 1
    assert body["longest_streak"] == 1
    assert body["last_active_date"] is not None


def test_ping_with_no_body_falls_back_to_utc(cleanup):
    user_id = f"streak_route_{uuid.uuid4().hex[:8]}"
    cleanup.append(user_id)
    _as_user(user_id)

    resp = client.post("/api/v1/streak/ping", json={})

    assert resp.status_code == 200
    assert resp.json()["current_streak"] == 1
