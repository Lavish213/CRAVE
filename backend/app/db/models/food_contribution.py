from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


INTENT_PRIVATE_LOG = "private_log"
INTENT_SOCIAL_POST = "social_post"
VALID_INTENTS = frozenset({INTENT_PRIVATE_LOG, INTENT_SOCIAL_POST})

REACTION_LOVED = "loved"
REACTION_GOOD = "good"
REACTION_NOT_FOR_ME = "not_for_me"
VALID_REACTIONS = frozenset({REACTION_LOVED, REACTION_GOOD, REACTION_NOT_FOR_ME})

VISIBILITY_PRIVATE = "private"
VISIBILITY_CONNECTIONS = "connections"
VISIBILITY_PUBLIC = "public"
VALID_VISIBILITIES = frozenset({VISIBILITY_PRIVATE, VISIBILITY_CONNECTIONS, VISIBILITY_PUBLIC})

STATUS_COMMITTED = "committed"
STATUS_DELETED = "deleted"
VALID_STATUSES = frozenset({STATUS_COMMITTED, STATUS_DELETED})


class FoodContribution(Base, TimestampMixin):
    """Canonical user contribution coordinating a food log or social post.

    Media keeps its own processing/moderation lifecycle in PlaceImage and
    PlaceVideo. Visit evidence keeps its own authority. This row records the
    user's explicit contribution semantics and references those authorities;
    it never substitutes for them.
    """

    __tablename__ = "food_contributions"
    __table_args__ = (
        Index("ix_food_contributions_user_created", "user_id", "created_at"),
        Index("ix_food_contributions_place_created", "place_id", "created_at"),
        Index("ix_food_contributions_visibility_created", "visibility", "created_at"),
        Index(
            "uq_food_contributions_user_client_id",
            "user_id",
            "client_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    place_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="CASCADE"), nullable=False
    )

    intent: Mapped[str] = mapped_column(String(24), nullable=False)
    reaction: Mapped[str | None] = mapped_column(String(24), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(24), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    image_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("place_images.id", ondelete="SET NULL"), nullable=True
    )
    video_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("place_videos.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=STATUS_COMMITTED, server_default=text("'committed'")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
