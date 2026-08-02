# app/db/models/activity_event.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

EVENT_RANKED_PLACE = "ranked_place"
EVENT_FOLLOWED_USER = "followed_user"
VALID_EVENT_TYPES = {EVENT_RANKED_PLACE, EVENT_FOLLOWED_USER}


class ActivityEvent(Base, TimestampMixin):
    """
    A single "user X did Y" event, written whenever a ranking finalizes or
    a follow is created. GET /feed/friends filters these to whoever the
    caller follows — the whole point of a friend graph existing at all.
    """

    __tablename__ = "activity_events"

    __table_args__ = (
        Index("ix_activity_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The actor — whoever did the ranking/following.
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True, index=True
    )

    target_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
