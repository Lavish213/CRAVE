# app/db/models/activity_event.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

EVENT_RANKED_PLACE = "ranked_place"
EVENT_FOLLOWED_USER = "followed_user"
EVENT_POSTED_FOOD = "posted_food"
VALID_EVENT_TYPES = {EVENT_RANKED_PLACE, EVENT_FOLLOWED_USER, EVENT_POSTED_FOOD}


class ActivityEvent(Base, TimestampMixin):
    """Chronological social index event, never the authority for user content.

    Rankings and follows point at their existing domain authorities. Posting V2
    uses ``posted_food`` only as a lightweight pointer to a FoodContribution;
    caption, visibility, reaction, media ownership, and deletion remain owned by
    FoodContribution/PlaceImage/PlaceVideo rather than being redefined here.
    GET /feed/friends filters these events to accounts the viewer follows.
    """

    __tablename__ = "activity_events"

    __table_args__ = (
        Index("ix_activity_events_user_created", "user_id", "created_at"),
        Index("ix_activity_events_user_id", "user_id"),
        Index("ix_activity_events_place_id", "place_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )
    target_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
