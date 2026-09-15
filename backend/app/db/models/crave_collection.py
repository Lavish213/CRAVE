from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class CraveCollection(Base, TimestampMixin):
    """User-owned Craves collection.

    This is intentionally separate from ``CraveItem``. ``CraveItem`` is the
    share/import pipeline; collections are the product-facing organization
    model for real places the user wants to remember.
    """

    __tablename__ = "crave_collections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_crave_collections_user_name"),
        Index("ix_crave_collections_user_sort", "user_id", "sort_order", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    places: Mapped[list["CraveCollectionPlace"]] = relationship(
        "CraveCollectionPlace",
        back_populates="collection",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CraveCollectionPlace(Base):
    __tablename__ = "crave_collection_places"
    __table_args__ = (
        Index("ix_crave_collection_places_state", "state_id"),
    )

    collection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("crave_collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    state_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("crave_place_states.id", ondelete="CASCADE"),
        primary_key=True,
    )

    collection: Mapped[CraveCollection] = relationship(
        "CraveCollection",
        back_populates="places",
    )
    state: Mapped["CravePlaceState"] = relationship(
        "CravePlaceState",
        back_populates="collection_links",
    )
