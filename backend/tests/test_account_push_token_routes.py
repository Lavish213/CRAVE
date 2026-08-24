"""
Coverage for the push-token registration endpoints added to
app/api/v1/routes/account.py.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.device_push_token import DevicePushToken

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
def token():
    yield f"ExponentPushToken[{uuid.uuid4().hex}]"


def _cleanup(db, token):
    db.query(DevicePushToken).filter(DevicePushToken.push_token == token).delete()
    db.commit()


def test_registering_a_token_stores_it(db, token):
    _as_user("route-user-a")
    try:
        resp = client.post(
            "/api/v1/account/push-token",
            json={"push_token": token, "platform": "ios"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        row = db.query(DevicePushToken).filter(DevicePushToken.push_token == token).one()
        assert row.user_id == "route-user-a"
        assert row.platform == "ios"
    finally:
        _cleanup(db, token)


def test_invalid_platform_is_rejected(token):
    _as_user("route-user-a")
    resp = client.post(
        "/api/v1/account/push-token",
        json={"push_token": token, "platform": "blackberry"},
    )
    assert resp.status_code == 400


def test_unregistering_removes_the_token(db, token):
    _as_user("route-user-a")
    client.post(
        "/api/v1/account/push-token",
        json={"push_token": token, "platform": "android"},
    )

    resp = client.delete(f"/api/v1/account/push-token/{token}")
    assert resp.status_code == 200
    assert db.query(DevicePushToken).filter(DevicePushToken.push_token == token).count() == 0


def test_unregistering_someone_elses_token_is_a_noop(db, token):
    _as_user("route-user-a")
    client.post(
        "/api/v1/account/push-token",
        json={"push_token": token, "platform": "android"},
    )

    try:
        _as_user("route-user-b")
        resp = client.delete(f"/api/v1/account/push-token/{token}")

        assert resp.status_code == 200
        assert db.query(DevicePushToken).filter(DevicePushToken.push_token == token).count() == 1
    finally:
        _cleanup(db, token)
