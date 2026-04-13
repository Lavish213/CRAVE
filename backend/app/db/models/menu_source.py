from __future__ import annotations

import uuid

from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

class MenuSource(Base, TimestampMixin):

    __tablename__ = "menu_sources"

    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "source_hash",
            name="uq_menu_source_place_hash",
        ),
        Index("ix_menu_source_place_id", "place_id"),
        Index("ix_menu_source_active", "is_active"),
        Index("ix_menu_source_type", "source_type"),
        Index("ix_menu_source_last_seen", "last_seen_at"),
    )

    # --------------------------------------------------
    # IDENTITY
    # --------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # SOURCE DATA
    # --------------------------------------------------

    source_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    source_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="website",
        server_default="website",
        index=True,
    )

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # RELATIONSHIP
    # --------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        lazy="joined",
        passive_deletes=True,
    )