"""
Coverage for app.services.social.block_service — required for App Store
review compliance (Guideline 1.2, User-Generated Content apps need a way
to block abusive users, not just report individual content). Also covers
the two places block_service changes existing behavior: blocking clears
any existing follow relationship in either direction, and follow_service
refuses a new follow between blocked users.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.user_block import UserBlock
from app.db.models.user_follow import UserFollow
from app.services.social import block_service, follow_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def users():
    suffix = uuid.uuid4().hex[:8]
    return {
        "alice": f"block-test-alice-{suffix}",
        "bob": f"block-test-bob-{suffix}",
        "carol": f"block-test-carol-{suffix}",
    }


@pytest.fixture(autouse=True)
def _cleanup(db):
    yield
    db.query(UserBlock).filter(UserBlock.blocker_id.like("block-test-%")).delete(
        synchronize_session=False
    )
    db.query(UserFollow).filter(UserFollow.follower_id.like("block-test-%")).delete(
        synchronize_session=False
    )
    db.commit()


def test_block_creates_relationship(db, users):
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])
    assert block_service.is_blocked(db, user_a=users["alice"], user_b=users["bob"])


def test_block_is_symmetric_for_enforcement(db, users):
    """is_blocked must be True regardless of which side asks — a blocked
    user losing visibility into the blocker is the point, not just the
    reverse."""
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])
    assert block_service.is_blocked(db, user_a=users["bob"], user_b=users["alice"])


def test_block_is_idempotent(db, users):
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])

    count = (
        db.query(UserBlock)
        .filter(UserBlock.blocker_id == users["alice"], UserBlock.blocked_id == users["bob"])
        .count()
    )
    assert count == 1


def test_cannot_block_self(db, users):
    with pytest.raises(ValueError, match="cannot block yourself"):
        block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["alice"])


def test_unblock_removes_relationship(db, users):
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])
    removed = block_service.unblock_user(db, blocker_id=users["alice"], blocked_id=users["bob"])
    assert removed is True
    assert not block_service.is_blocked(db, user_a=users["alice"], user_b=users["bob"])


def test_unblock_nonexistent_returns_false(db, users):
    removed = block_service.unblock_user(db, blocker_id=users["alice"], blocked_id=users["bob"])
    assert removed is False


def test_list_blocked(db, users):
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["carol"])

    assert set(block_service.list_blocked(db, users["alice"])) == {users["bob"], users["carol"]}
    assert block_service.list_blocked(db, users["bob"]) == []


def test_blocked_user_ids_either_direction(db, users):
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])

    assert block_service.blocked_user_ids_either_direction(db, users["alice"]) == [users["bob"]]
    assert block_service.blocked_user_ids_either_direction(db, users["bob"]) == [users["alice"]]
    assert block_service.blocked_user_ids_either_direction(db, users["carol"]) == []


def test_blocking_removes_existing_follow_both_directions(db, users):
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])
    follow_service.follow_user(db, follower_id=users["bob"], followee_id=users["alice"])

    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])

    assert not follow_service.is_following(db, follower_id=users["alice"], followee_id=users["bob"])
    assert not follow_service.is_following(db, follower_id=users["bob"], followee_id=users["alice"])


def test_blocking_does_not_affect_unrelated_follows(db, users):
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["carol"])
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])

    assert follow_service.is_following(db, follower_id=users["alice"], followee_id=users["carol"])


def test_cannot_follow_a_user_who_blocked_you(db, users):
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])

    with pytest.raises(ValueError, match="cannot follow a blocked user"):
        follow_service.follow_user(db, follower_id=users["bob"], followee_id=users["alice"])


def test_cannot_follow_a_user_you_blocked(db, users):
    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])

    with pytest.raises(ValueError, match="cannot follow a blocked user"):
        follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])
