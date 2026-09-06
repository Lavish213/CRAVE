"""Regression coverage for complete, retryable account deletion."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.session import SessionLocal
from app.db.models.activity_event import ActivityEvent, EVENT_FOLLOWED_USER
from app.db.models.crave_item import CraveItem
from app.db.models.device_push_token import DevicePushToken
from app.db.models.hitlist_dedup_key import HitlistDedupKey
from app.db.models.hitlist_save import HitlistSave
from app.db.models.hitlist_suggestion import HitlistSuggestion
from app.db.models.recommendation_event import (
    EVENT_SAVE,
    SURFACE_CRAVES,
    RecommendationEvent,
)
from app.db.models.user_block import UserBlock
from app.db.models.user_follow import UserFollow
from app.db.models.user_profile import UserProfile
from app.db.models.user_streak import UserStreak
from app.services.account.account_deletion_service import delete_account
from app.services.social import block_service, follow_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def user_id():
    return f"account-delete-test-{uuid.uuid4().hex[:8]}"


def _mock_response(status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def _configure_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")


def test_delete_account_removes_profile_social_and_personal_rows(db, user_id, monkeypatch):
    _configure_supabase(monkeypatch)
    other = f"account-delete-test-other-{uuid.uuid4().hex[:8]}"

    db.add(UserProfile(id=user_id, username=f"u{uuid.uuid4().hex[:8]}"))
    db.add(UserStreak(user_id=user_id, current_streak=2, longest_streak=5))
    db.add(DevicePushToken(push_token=f"ExponentPushToken[{uuid.uuid4().hex}]", user_id=user_id, platform="ios"))
    db.add(HitlistSave(user_id=user_id, place_name="Saved Place", dedup_key=f"save:{uuid.uuid4()}"))
    db.add(HitlistSuggestion(user_id=user_id, place_name="Suggested Place"))
    db.add(HitlistDedupKey(user_id=user_id, dedup_key=f"key:{uuid.uuid4()}"))
    db.add(CraveItem(url="https://example.com/food", submitted_by=user_id))
    db.add(ActivityEvent(user_id=user_id, event_type=EVENT_FOLLOWED_USER, target_user_id=other))
    db.add(RecommendationEvent(user_id=user_id, surface=SURFACE_CRAVES, event_type=EVENT_SAVE))
    db.commit()

    follow_service.follow_user(db, follower_id=user_id, followee_id=other)
    follow_service.follow_user(db, follower_id=other, followee_id=user_id)
    block_service.block_user(db, blocker_id=user_id, blocked_id=other)

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(204),
    ), patch(
        "app.services.account.account_deletion_service.delete_object"
    ) as mock_storage_delete:
        result = delete_account(db, user_id)

    mock_storage_delete.assert_not_called()
    assert result == {
        "app_data_deleted": True,
        "storage_deleted": True,
        "supabase_account_deleted": True,
        "complete": True,
    }
    assert db.query(UserProfile).filter(UserProfile.id == user_id).one_or_none() is None
    assert db.query(UserStreak).filter(UserStreak.user_id == user_id).one_or_none() is None
    assert db.query(DevicePushToken).filter(DevicePushToken.user_id == user_id).count() == 0
    assert db.query(HitlistSave).filter(HitlistSave.user_id == user_id).count() == 0
    assert db.query(HitlistSuggestion).filter(HitlistSuggestion.user_id == user_id).count() == 0
    assert db.query(HitlistDedupKey).filter(HitlistDedupKey.user_id == user_id).count() == 0
    assert db.query(CraveItem).filter(CraveItem.submitted_by == user_id).count() == 0
    assert db.query(ActivityEvent).filter(ActivityEvent.user_id == user_id).count() == 0
    assert db.query(RecommendationEvent).filter(RecommendationEvent.user_id == user_id).count() == 0
    assert not follow_service.is_following(db, follower_id=user_id, followee_id=other)
    assert not follow_service.is_following(db, follower_id=other, followee_id=user_id)
    assert not block_service.is_blocked(db, user_a=user_id, user_b=other)


def test_storage_failure_fails_closed_before_database_or_auth_delete(db, user_id, monkeypatch):
    _configure_supabase(monkeypatch)
    db.add(UserProfile(id=user_id, username=f"u{uuid.uuid4().hex[:8]}"))
    db.commit()

    with patch(
        "app.services.account.account_deletion_service._delete_r2_objects",
        return_value=False,
    ), patch(
        "app.services.account.account_deletion_service.requests.delete"
    ) as mock_auth_delete:
        result = delete_account(db, user_id)

    assert result["complete"] is False
    assert result["storage_deleted"] is False
    assert result["app_data_deleted"] is False
    mock_auth_delete.assert_not_called()
    assert db.query(UserProfile).filter(UserProfile.id == user_id).one_or_none() is not None


def test_supabase_failure_is_reported_as_incomplete_and_retryable(db, user_id, monkeypatch):
    _configure_supabase(monkeypatch)
    db.add(UserProfile(id=user_id, username=f"u{uuid.uuid4().hex[:8]}"))
    db.commit()

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(500),
    ):
        result = delete_account(db, user_id)

    assert result["app_data_deleted"] is True
    assert result["storage_deleted"] is True
    assert result["supabase_account_deleted"] is False
    assert result["complete"] is False
    assert db.query(UserProfile).filter(UserProfile.id == user_id).one_or_none() is None


def test_delete_account_reports_incomplete_when_supabase_not_configured(db, user_id, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with patch("app.services.account.account_deletion_service.requests.delete") as mock_delete:
        result = delete_account(db, user_id)

    mock_delete.assert_not_called()
    assert result["complete"] is False
    assert result["supabase_account_deleted"] is False


def test_delete_account_is_idempotent(db, user_id, monkeypatch):
    _configure_supabase(monkeypatch)
    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(204),
    ):
        first = delete_account(db, user_id)
        second = delete_account(db, user_id)

    assert first["complete"] is True
    assert second["complete"] is True
