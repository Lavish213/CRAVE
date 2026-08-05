from __future__ import annotations

import uuid

from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

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
        # Composite — added by a dedicated migration (add_missing_pg_indexes)
        # but never declared here, so alembic autogenerate wanted to DROP a
        # real, deployed, useful index just because the model didn't know
        # about it.
        Index("ix_menu_source_place_active", "place_id", "is_active"),
        # Explicit names below — index=True on these columns would route
        # through Base's naming convention and mismatch what's actually
        # deployed (see NAMING_CONVENTION's comment in app/db/models/base.py).
        Index("ix_menu_source_provider", "provider"),
        Index("ix_menu_source_confidence", "confidence"),
        Index("ix_menu_source_last_verified", "last_verified_at"),
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

    # provider: specific platform name (toast, square, chownow, popmenu, clover, html, grubhub)
    # source_type: broad category (provider_api, html, aggregator)
    provider: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="website",
        server_default="website",
        index=True,
    )

    # confidence: discovery confidence [0.0, 1.0]
    # Toast direct redirect = 1.0, HTML link = 0.9, JSON-LD = 0.7
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )

    # --------------------------------------------------
    # LIFECYCLE TIMESTAMPS
    # --------------------------------------------------

    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------------------------------------------
    # FAILURE TRACKING
    # --------------------------------------------------

    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invalidation_reason: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
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