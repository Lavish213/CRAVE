"""
Coverage for app.services.notifications.push_token_service --
register/unregister of Expo push tokens (see device_push_token.py's
docstring for why the row is keyed by the token, not (user_id, token)).
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.device_push_token import DevicePushToken
from app.services.notifications.push_token_service import (
    register_push_token,
    unregister_push_token,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def token(db):
    t = f"ExponentPushToken[{uuid.uuid4().hex}]"
    yield t
    db.query(DevicePushToken).filter(DevicePushToken.push_token == t).delete()
    db.commit()


def test_register_creates_a_new_row(db, token):
    register_push_token(db, user_id="user-a", push_token=token, platform="ios")

    row = db.query(DevicePushToken).filter(DevicePushToken.push_token == token).one()
    assert row.user_id == "user-a"
    assert row.platform == "ios"


def test_registering_the_same_token_again_updates_it(db, token):
    register_push_token(db, user_id="user-a", push_token=token, platform="ios")
    register_push_token(db, user_id="user-a", push_token=token, platform="android")

    rows = db.query(DevicePushToken).filter(DevicePushToken.push_token == token).all()
    assert len(rows) == 1
    assert rows[0].platform == "android"


def test_registering_the_same_token_under_a_different_user_moves_it(db, token):
    """A device that logs out of one account and into another must not
    keep sending that first account's notifications."""
    register_push_token(db, user_id="user-a", push_token=token, platform="ios")
    register_push_token(db, user_id="user-b", push_token=token, platform="ios")

    rows = db.query(DevicePushToken).filter(DevicePushToken.push_token == token).all()
    assert len(rows) == 1
    assert rows[0].user_id == "user-b"


def test_register_rejects_an_invalid_platform(db, token):
    with pytest.raises(ValueError):
        register_push_token(db, user_id="user-a", push_token=token, platform="windows-phone")


def test_unregister_removes_the_row(db, token):
    register_push_token(db, user_id="user-a", push_token=token, platform="ios")

    unregister_push_token(db, user_id="user-a", push_token=token)

    assert db.query(DevicePushToken).filter(DevicePushToken.push_token == token).count() == 0


def test_unregister_is_a_noop_for_a_token_belonging_to_another_user(db, token):
    register_push_token(db, user_id="user-a", push_token=token, platform="ios")

    unregister_push_token(db, user_id="user-b", push_token=token)

    assert db.query(DevicePushToken).filter(DevicePushToken.push_token == token).count() == 1
