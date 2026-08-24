# app/services/social/follow_service.py
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.db.models.user_follow import UserFollow
from app.services.social.block_service import is_blocked


def follow_user(db: Session, *, follower_id: str, followee_id: str) -> tuple[UserFollow, bool]:
    """
    Returns (follow, created). `created` is False when the follow already
    existed -- callers must check it before writing any first-time-only
    side effect (e.g. an activity feed event): without it, a client retry
    of an already-successful follow (the request landed, but the response
    was lost) would re-record that side effect every time, since this
    function's own idempotency (returning the existing row instead of
    erroring) gives no signal that nothing actually changed this call.
    """
    if follower_id == followee_id:
        raise ValueError("cannot follow yourself")

    if is_blocked(db, user_a=follower_id, user_b=followee_id):
        raise ValueError("cannot follow a blocked user")

    existing = (
        db.query(UserFollow)
        .filter(UserFollow.follower_id == follower_id, UserFollow.followee_id == followee_id)
        .one_or_none()
    )
    if existing:
        return existing, False

    follow = UserFollow(follower_id=follower_id, followee_id=followee_id)
    db.add(follow)
    db.commit()
    return follow, True


def unfollow_user(db: Session, *, follower_id: str, followee_id: str) -> bool:
    existing = (
        db.query(UserFollow)
        .filter(UserFollow.follower_id == follower_id, UserFollow.followee_id == followee_id)
        .one_or_none()
    )
    if not existing:
        return False

    db.delete(existing)
    db.commit()
    return True


def is_following(db: Session, *, follower_id: str, followee_id: str) -> bool:
    return (
        db.query(UserFollow.id)
        .filter(UserFollow.follower_id == follower_id, UserFollow.followee_id == followee_id)
        .first()
        is not None
    )


def list_following(db: Session, user_id: str, *, limit: int = 50, offset: int = 0) -> List[str]:
    rows = (
        db.query(UserFollow.followee_id)
        .filter(UserFollow.follower_id == user_id)
        .order_by(UserFollow.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]


def list_followers(db: Session, user_id: str, *, limit: int = 50, offset: int = 0) -> List[str]:
    rows = (
        db.query(UserFollow.follower_id)
        .filter(UserFollow.followee_id == user_id)
        .order_by(UserFollow.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]
