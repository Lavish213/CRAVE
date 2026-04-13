from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
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


class MenuSnapshot(Base):
    __tablename__ = "menu_snapshots"

    __table_args__ = (
        Index("ix_menu_snapshots_place_created", "place_id", "created_at"),
        Index("ix_menu_snapshots_method", "extraction_method"),
        Index("ix_menu_snapshots_success", "success"),
        Index("ix_menu_snapshots_lookup", "place_id", "created_at"),
        Index("ix_menu_snapshots_source_url", "source_url"),
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
    # EXTRACTION METADATA
    # --------------------------------------------------

    extraction_method: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    item_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    # --------------------------------------------------
    # DATA PAYLOADS
    # --------------------------------------------------

    raw_payload: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    normalized_items: Mapped[list[dict] | None] = mapped_column(
        JSON().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # --------------------------------------------------
    # PERFORMANCE / DEBUG
    # --------------------------------------------------

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    extractor_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # --------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    # --------------------------------------------------
    # RELATIONSHIP
    # --------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        lazy="selectin",
        passive_deletes=True,
    )