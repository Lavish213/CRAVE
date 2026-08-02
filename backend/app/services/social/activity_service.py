# app/services/social/activity_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.activity_event import ActivityEvent, EVENT_FOLLOWED_USER, EVENT_RANKED_PLACE


def record_ranked_place(
    db: Session, *, user_id: str, place_id: str, tier: str, score: float
) -> ActivityEvent:
    event = ActivityEvent(
        user_id=user_id,
        event_type=EVENT_RANKED_PLACE,
        place_id=place_id,
        payload={"tier": tier, "score": score},
    )
    db.add(event)
    db.flush()
    return event


def record_followed_user(db: Session, *, user_id: str, target_user_id: str) -> ActivityEvent:
    event = ActivityEvent(
        user_id=user_id,
        event_type=EVENT_FOLLOWED_USER,
        target_user_id=target_user_id,
    )
    db.add(event)
    db.flush()
    return event


def list_friend_feed(
    db: Session, *, follower_ids: list[str], limit: int = 30, offset: int = 0
) -> list[ActivityEvent]:
    if not follower_ids:
        return []
    return (
        db.query(ActivityEvent)
        .filter(ActivityEvent.user_id.in_(follower_ids))
        .order_by(ActivityEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
