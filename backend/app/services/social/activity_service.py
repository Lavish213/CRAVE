# app/services/social/activity_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.activity_event import (
    ActivityEvent,
    EVENT_FOLLOWED_USER,
    EVENT_POSTED_FOOD,
    EVENT_RANKED_PLACE,
)


def record_ranked_place(
    db: Session, *, user_id: str, place_id: str, tier: str, score: float
) -> ActivityEvent:
    """Append one ranking activity pointer."""
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
    """Append one follow activity pointer."""
    event = ActivityEvent(
        user_id=user_id,
        event_type=EVENT_FOLLOWED_USER,
        target_user_id=target_user_id,
    )
    db.add(event)
    db.flush()
    return event


def record_posted_food(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    contribution_id: str,
    visibility: str,
    reaction: str | None,
) -> ActivityEvent:
    """Index a committed social FoodContribution without duplicating its content."""
    event = ActivityEvent(
        user_id=user_id,
        event_type=EVENT_POSTED_FOOD,
        place_id=place_id,
        payload={
            "contribution_id": contribution_id,
            "visibility": visibility,
            "reaction": reaction,
        },
    )
    db.add(event)
    db.flush()
    return event


def retract_posted_food(db: Session, *, user_id: str, contribution_id: str) -> int:
    """Remove social index events pointing at a deleted FoodContribution."""
    candidates = (
        db.query(ActivityEvent)
        .filter(
            ActivityEvent.user_id == user_id,
            ActivityEvent.event_type == EVENT_POSTED_FOOD,
        )
        .all()
    )
    ids = [event.id for event in candidates if (event.payload or {}).get("contribution_id") == contribution_id]
    if not ids:
        return 0
    return (
        db.query(ActivityEvent)
        .filter(ActivityEvent.id.in_(ids))
        .delete(synchronize_session=False)
    )


def list_friend_feed(
    db: Session, *, follower_ids: list[str], limit: int = 30, offset: int = 0
) -> list[ActivityEvent]:
    """Return chronological events authored by accounts the viewer follows."""
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
