from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# CraveItem — stores user-submitted shared URLs for parsing and place matching
class CraveItem(Base):
    """
    Stores a user-submitted URL (Instagram, TikTok, blog, etc.) that
    references a restaurant. The share_parser_worker processes pending items,
    extracts a place name from the page metadata, and attempts to match it
    against an existing Place record.
    """

    __tablename__ = "crave_items"

    __table_args__ = (
        Index("ix_crave_items_status", "status"),
        Index("ix_crave_items_created_at", "created_at"),
        Index("ix_crave_items_matched_place_id", "matched_place_id"),
    )

    # ------------------------------------------------------------------
    # IDENTITY
    # ------------------------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # ------------------------------------------------------------------
    # SUBMISSION DATA
    # ------------------------------------------------------------------

    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="web",
        server_default="web",
        doc="'instagram', 'tiktok', 'youtube', 'twitter', 'web', 'other'",
    )

    submitted_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="User identifier — no auth system yet, stored as-is",
    )

    # ------------------------------------------------------------------
    # PARSED / SCRAPED DATA
    # ------------------------------------------------------------------

    raw_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Scraped page content or metadata",
    )

    parsed_place_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Restaurant name extracted from page content",
    )

    parsed_city_hint: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="City mentioned in the content",
    )

    # ------------------------------------------------------------------
    # PLACE MATCH
    # ------------------------------------------------------------------

    matched_place_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    match_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="0.0–1.0 confidence score for the place match",
    )

    # ------------------------------------------------------------------
    # STATUS / LIFECYCLE
    # ------------------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
        doc="'pending', 'matched', 'unmatched', 'error'",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("(CURRENT_TIMESTAMP)"),
        index=True,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # RELATIONSHIP
    # ------------------------------------------------------------------

    matched_place: Mapped["Place | None"] = relationship(
        "Place",
        foreign_keys=[matched_place_id],
        passive_deletes=True,
        lazy="select",
    )

    # ------------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------------

    def __init__(
        self,
        *,
        url: str,
        source_type: str = "web",
        submitted_by: str | None = None,
        id: str | None = None,
    ):
        if not url:
            raise ValueError("CraveItem requires a URL")

        self.id = id or str(uuid.uuid4())
        self.url = url.strip()
        self.source_type = (source_type or "web").strip().lower()
        self.submitted_by = submitted_by
        self.status = "pending"
