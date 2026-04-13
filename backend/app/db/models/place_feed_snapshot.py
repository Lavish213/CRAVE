from __future__ import annotations

import uuid
from datetime import datetime, timezone


from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Boolean,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlaceFeedSnapshot(Base):
    """
    FINALIZED PRODUCTION SNAPSHOT MODEL

    Guarantees:
    - Append-only (no updates after insert)
    - Full ingestion audit trail
    - Replay-safe
    - Multi-source ingestion safe

    Optimized for:
    - debugging pipelines
    - reprocessing
    - source comparison
    """

    __tablename__ = "place_feed_snapshots"

    __table_args__ = (
        Index("ix_snapshot_place_id", "place_id"),
        Index("ix_snapshot_source", "source"),
        Index("ix_snapshot_created_at", "created_at"),

        # 🔥 CRITICAL FOR REPLAY + LOOKUPS
        Index("ix_snapshot_lookup", "place_id", "source", "created_at"),

        # 🔥 OPTIONAL DEDUPE GUARD (safe, non-blocking)
        Index("ix_snapshot_external", "external_id"),
    )

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # SOURCE TRACKING
    # -----------------------------------------------------

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    external_id: Mapped[str | None] = mapped_column(
    String(128),
    nullable=True,
    index=True,
    )

    # -----------------------------------------------------
    # SNAPSHOT PAYLOAD
    # -----------------------------------------------------

    payload: Mapped[dict] = mapped_column(
    JSON,
    nullable=False,
    )

    # -----------------------------------------------------
    # METADATA
    # -----------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    # -----------------------------------------------------
    # RELATIONSHIP
    # -----------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        back_populates="feed_snapshots",
        passive_deletes=True,
        lazy="selectin",
    )