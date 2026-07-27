from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    String,
    text,
)

# Valid visibility_status values (enforced at service layer, not DB enum)
VISIBILITY_HIDDEN = "hidden"
VISIBILITY_GALLERY_ONLY = "gallery_only"
VISIBILITY_CANDIDATE_PRIMARY = "candidate_primary"
VISIBILITY_SHOWCASE = "showcase"

VISIBILITY_STATES = frozenset({
    VISIBILITY_HIDDEN,
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_CANDIDATE_PRIMARY,
    VISIBILITY_SHOWCASE,
})

# States that may appear in public surfaces (not hidden)
VISIBILITY_PUBLIC = frozenset({
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_CANDIDATE_PRIMARY,
    VISIBILITY_SHOWCASE,
})

# States eligible to be primary image
VISIBILITY_PRIMARY_ELIGIBLE = frozenset({
    VISIBILITY_CANDIDATE_PRIMARY,
    VISIBILITY_SHOWCASE,
})
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

class PlaceImage(Base, TimestampMixin):
    __tablename__ = "place_images"

    __table_args__ = (
        Index("uq_place_image_place_url", "place_id", "url", unique=True),
        Index("ix_place_images_place_primary", "place_id", "is_primary"),
        Index("ix_place_images_confidence", "confidence"),
        Index("ix_place_images_created", "created_at"),
        Index("ix_place_images_visibility_status", "visibility_status"),
        Index("ix_place_images_place_visibility", "place_id", "visibility_status"),
        Index("ix_place_images_place_order", "place_id", "insertion_order"),
    )

    # --------------------------------------------------
    # IDENTITY
    # --------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # IMAGE DATA
    # --------------------------------------------------

    url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    # --------------------------------------------------
    # FLAGS / SCORING
    # --------------------------------------------------

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        server_default=text("0.5"),
        index=True,
    )

    # --------------------------------------------------
    # VISIBILITY SYSTEM (Phase 1)
    # --------------------------------------------------

    visibility_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=VISIBILITY_GALLERY_ONLY,
        server_default=text(f"'{VISIBILITY_GALLERY_ONLY}'"),
        index=True,
    )

    # Content-based quality score (0.0–1.0). Null until scored by heuristics (Phase 3).
    quality_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )

    # Semantic content bucket (e.g. "food", "interior", "menu", "exterior").
    # Null until classified (Phase 3).
    content_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        default=None,
    )

    # --------------------------------------------------
    # ORDERING (PostgreSQL migration safety)
    # --------------------------------------------------
    # SQLite has rowid which encodes Google's quality rank (insertion order per place).
    # PostgreSQL has no rowid. insertion_order is assigned at ingest time
    # and backfilled from rowid during SQLite→PostgreSQL migration.
    # Use insertion_order ASC (not rowid, not uuid, not created_at) for position-based ranking.
    insertion_order: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        index=True,
    )

    # --------------------------------------------------
    # RELATIONSHIP
    # --------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        back_populates="images",
        lazy="selectin",
        passive_deletes=True,
    )