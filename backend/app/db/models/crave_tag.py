from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class CraveTag(Base, TimestampMixin):
    __tablename__ = "crave_tags"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_crave_tags_user_name"),
        Index("ix_crave_tags_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    color: Mapped[str | None] = mapped_column(String(24), nullable=True)

    places: Mapped[list["CravePlaceTag"]] = relationship(
        "CravePlaceTag",
        back_populates="tag",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CravePlaceTag(Base):
    __tablename__ = "crave_place_tags"
    __table_args__ = (
        Index("ix_crave_place_tags_state", "state_id"),
    )

    tag_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("crave_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    state_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("crave_place_states.id", ondelete="CASCADE"),
        primary_key=True,
    )

    tag: Mapped[CraveTag] = relationship("CraveTag", back_populates="places")
    state: Mapped["CravePlaceState"] = relationship(
        "CravePlaceState",
        back_populates="tag_links",
    )
