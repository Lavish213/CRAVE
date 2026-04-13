from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

# -----------------------------------------------------
# TIME
# -----------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# -----------------------------------------------------
# MODEL
# -----------------------------------------------------

class PlaceImageFetchLog(Base):
    """
    Tracks image fetch attempts per place + source.

    Purpose:
    - Prevent over-fetching / scraping abuse
    - Enable refresh windows (e.g. 24h rules)
    - Support multi-provider pipelines

    Design:
    - Append-only log
    - High-write safe
    - Query-optimized for "last fetch"
    """

    __tablename__ = "place_image_fetch_logs"

    __table_args__ = (
        # -------------------------------------------------
        # FAST LOOKUPS
        # -------------------------------------------------
        Index("ix_img_fetch_place", "place_id"),
        Index("ix_img_fetch_source", "source"),
        Index("ix_img_fetch_time", "fetched_at"),

        # 🔥 CRITICAL: latest fetch lookup optimization
        Index(
            "ix_img_fetch_place_source_time",
            "place_id",
            "source",
            "fetched_at",
        ),
    )

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # -----------------------------------------------------
    # RELATION
    # -----------------------------------------------------

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------
    # SOURCE
    # -----------------------------------------------------

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="image source (website, google, yelp, etc)",
    )

    # -----------------------------------------------------
    # FETCH TIME
    # -----------------------------------------------------

    fetched_at: Mapped[datetime] = mapped_column(
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
        lazy="selectin",
        passive_deletes=True,
    )