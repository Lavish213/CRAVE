from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, JSONType, TimestampMixin


CRAVE_STATUS_WANT_TO_TRY = "want_to_try"
CRAVE_STATUS_TRIED = "tried"

CRAVE_ALLOWED_STATUSES = (CRAVE_STATUS_WANT_TO_TRY, CRAVE_STATUS_TRIED)


class CravePlaceState(Base, TimestampMixin):
    """Per-user product state for a real Place inside Craves.

    The older ``HitlistSave`` row answers "is this saved?". This table answers
    richer Craves questions: want-to-try vs tried, notes, favorite dishes, and
    organization into tags/collections.
    """

    __tablename__ = "crave_place_states"
    __table_args__ = (
        UniqueConstraint("user_id", "place_id", name="uq_crave_place_states_user_place"),
        CheckConstraint(
            "status in ('want_to_try', 'tried')",
            name="ck_crave_place_states_status",
        ),
        Index("ix_crave_place_states_user_status", "user_id", "status", "updated_at"),
        Index("ix_crave_place_states_place_id", "place_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=CRAVE_STATUS_WANT_TO_TRY,
        server_default=CRAVE_STATUS_WANT_TO_TRY,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    favorite_dishes: Mapped[list[str]] = mapped_column(
        JSONType,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
        doc="Ordered list of user-entered favorite dish names for this place.",
    )

    collection_links: Mapped[list["CraveCollectionPlace"]] = relationship(
        "CraveCollectionPlace",
        back_populates="state",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tag_links: Mapped[list["CravePlaceTag"]] = relationship(
        "CravePlaceTag",
        back_populates="state",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
