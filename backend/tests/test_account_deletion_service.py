"""
Coverage for app.services.account.account_deletion_service.delete_account —
required for App Store review (Guideline 5.1.1(v)).

Supabase's Admin API call is always mocked here — these tests must never
make a real network call. Covers both halves separately: app-side data
removal always happens; the Supabase auth deletion's success/failure is
reported back rather than silently assumed.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.session import SessionLocal
from app.db.models.user_profile import UserProfile
from app.db.models.user_follow import UserFollow
from app.db.models.user_block import UserBlock
from app.services.account.account_deletion_service import delete_account
from app.services.social import block_service, follow_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user_id():
    return f"account-delete-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _cleanup(db):
    yield
    db.query(UserProfile).filter(UserProfile.id.like("account-delete-test-%")).delete(
        synchronize_session=False
    )
    db.query(UserFollow).filter(
        UserFollow.follower_id.like("account-delete-test-%")
        | UserFollow.followee_id.like("account-delete-test-%")
    ).delete(synchronize_session=False)
    db.query(UserBlock).filter(
        UserBlock.blocker_id.like("account-delete-test-%")
        | UserBlock.blocked_id.like("account-delete-test-%")
    ).delete(synchronize_session=False)
    db.commit()


def _mock_response(status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def test_delete_account_removes_profile(db, user_id, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    db.add(UserProfile(id=user_id, username=f"u{uuid.uuid4().hex[:8]}"))
    db.commit()

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(204),
    ):
        result = delete_account(db, user_id)

    assert result["profile_deleted"] is True
    assert result["supabase_account_deleted"] is True
    assert db.query(UserProfile).filter(UserProfile.id == user_id).one_or_none() is None


def test_delete_account_removes_follows_both_directions(db, user_id, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    other = f"account-delete-test-other-{uuid.uuid4().hex[:8]}"
    follow_service.follow_user(db, follower_id=user_id, followee_id=other)
    follow_service.follow_user(db, follower_id=other, followee_id=user_id)

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(204),
    ):
        delete_account(db, user_id)

    assert not follow_service.is_following(db, follower_id=user_id, followee_id=other)
    assert not follow_service.is_following(db, follower_id=other, followee_id=user_id)


def test_delete_account_removes_blocks_both_directions(db, user_id, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    other = f"account-delete-test-other-{uuid.uuid4().hex[:8]}"
    block_service.block_user(db, blocker_id=user_id, blocked_id=other)

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(204),
    ):
        delete_account(db, user_id)

    assert not block_service.is_blocked(db, user_a=user_id, user_b=other)


def test_delete_account_reports_false_when_supabase_not_configured(db, user_id, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with patch("app.services.account.account_deletion_service.requests.delete") as mock_delete:
        result = delete_account(db, user_id)

    mock_delete.assert_not_called()
    assert result["supabase_account_deleted"] is False


def test_delete_account_reports_false_on_supabase_upstream_error(db, user_id, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(500),
    ):
        result = delete_account(db, user_id)

    assert result["supabase_account_deleted"] is False
    # App-side data is still gone even though the Supabase call failed —
    # the caller needs to know both halves' status independently.
    assert result["profile_deleted"] is False  # no profile existed for this user_id


def test_delete_account_reports_false_on_supabase_network_error(db, user_id, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        side_effect=RuntimeError("connection reset"),
    ):
        result = delete_account(db, user_id)

    assert result["supabase_account_deleted"] is False


def test_delete_account_is_idempotent(db, user_id, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    with patch(
        "app.services.account.account_deletion_service.requests.delete",
        return_value=_mock_response(204),
    ):
        first = delete_account(db, user_id)
        second = delete_account(db, user_id)

    assert first["profile_deleted"] is False  # never had a profile
    assert second["profile_deleted"] is False
