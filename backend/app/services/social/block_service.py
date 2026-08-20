# app/services/social/block_service.py
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.db.models.user_block import UserBlock
from app.db.models.user_follow import UserFollow


def block_user(db: Session, *, blocker_id: str, blocked_id: str) -> UserBlock:
    if blocker_id == blocked_id:
        raise ValueError("cannot block yourself")

    existing = (
        db.query(UserBlock)
        .filter(UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id)
        .one_or_none()
    )
    if existing:
        return existing

    block = UserBlock(blocker_id=blocker_id, blocked_id=blocked_id)
    db.add(block)

    # A block ends any existing follow relationship in either direction —
    # otherwise a blocked user's activity could still surface through the
    # friends feed (which reads UserFollow directly, not through block
    # checks) even though everything else now hides them.
    db.query(UserFollow).filter(
        UserFollow.follower_id.in_([blocker_id, blocked_id]),
        UserFollow.followee_id.in_([blocker_id, blocked_id]),
    ).delete(synchronize_session=False)

    db.commit()
    return block


def unblock_user(db: Session, *, blocker_id: str, blocked_id: str) -> bool:
    existing = (
        db.query(UserBlock)
        .filter(UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id)
        .one_or_none()
    )
    if not existing:
        return False

    db.delete(existing)
    db.commit()
    return True


def is_blocked(db: Session, *, user_a: str, user_b: str) -> bool:
    """True if either user has blocked the other. Enforcement is symmetric
    on purpose — a blocked user losing visibility into the person who
    blocked them is the whole point, not just the reverse."""
    return (
        db.query(UserBlock.id)
        .filter(
            UserBlock.blocker_id.in_([user_a, user_b]),
            UserBlock.blocked_id.in_([user_a, user_b]),
        )
        .first()
        is not None
    )


def list_blocked(db: Session, blocker_id: str, *, limit: int = 100, offset: int = 0) -> List[str]:
    rows = (
        db.query(UserBlock.blocked_id)
        .filter(UserBlock.blocker_id == blocker_id)
        .order_by(UserBlock.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]


def blocked_user_ids_either_direction(db: Session, user_id: str) -> List[str]:
    """Every user_id that should be filtered out of user_id's feeds/search —
    people they blocked AND people who blocked them."""
    blocked_by_me = (
        db.query(UserBlock.blocked_id).filter(UserBlock.blocker_id == user_id).all()
    )
    blocked_me = (
        db.query(UserBlock.blocker_id).filter(UserBlock.blocked_id == user_id).all()
    )
    return list({r[0] for r in blocked_by_me} | {r[0] for r in blocked_me})
