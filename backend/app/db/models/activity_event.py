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
        # Explicit names (not the index=True shorthand below, which would
        # route through Base's naming convention and mismatch what the
        # migration actually deployed — see NAMING_CONVENTION's comment in
        # app/db/models/base.py for why these two tables' index names don't
        # follow the convention's doubled-table-name pattern).
        Index("ix_activity_events_user_id", "user_id"),
        Index("ix_activity_events_place_id", "place_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The actor — whoever did the ranking/following.
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )

    target_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
