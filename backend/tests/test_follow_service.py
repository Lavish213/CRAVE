"""
Coverage for app.services.social.follow_service — the friend graph that
didn't exist at all before this pass. Nothing social (feed, leaderboard,
place-level friend score) means anything without this.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.user_follow import UserFollow
from app.services.social import follow_service


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
        "alice": f"follow-test-alice-{suffix}",
        "bob": f"follow-test-bob-{suffix}",
        "carol": f"follow-test-carol-{suffix}",
    }


@pytest.fixture(autouse=True)
def _cleanup(db):
    yield
    db.query(UserFollow).filter(UserFollow.follower_id.like("follow-test-%")).delete(
        synchronize_session=False
    )
    db.commit()


def test_follow_creates_relationship(db, users):
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])
    assert follow_service.is_following(db, follower_id=users["alice"], followee_id=users["bob"])
    assert not follow_service.is_following(db, follower_id=users["bob"], followee_id=users["alice"])


def test_follow_is_idempotent(db, users):
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])

    count = (
        db.query(UserFollow)
        .filter(
            UserFollow.follower_id == users["alice"], UserFollow.followee_id == users["bob"]
        )
        .count()
    )
    assert count == 1


def test_cannot_follow_self(db, users):
    with pytest.raises(ValueError, match="cannot follow yourself"):
        follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["alice"])


def test_unfollow_removes_relationship(db, users):
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])
    removed = follow_service.unfollow_user(db, follower_id=users["alice"], followee_id=users["bob"])
    assert removed is True
    assert not follow_service.is_following(db, follower_id=users["alice"], followee_id=users["bob"])


def test_unfollow_nonexistent_returns_false(db, users):
    removed = follow_service.unfollow_user(db, follower_id=users["alice"], followee_id=users["bob"])
    assert removed is False


def test_list_following_and_followers(db, users):
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["carol"])
    follow_service.follow_user(db, follower_id=users["bob"], followee_id=users["carol"])

    assert set(follow_service.list_following(db, users["alice"])) == {users["bob"], users["carol"]}
    assert set(follow_service.list_followers(db, users["carol"])) == {users["alice"], users["bob"]}
    assert follow_service.list_following(db, users["carol"]) == []
