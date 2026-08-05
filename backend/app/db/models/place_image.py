from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
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

    # Nullable: legacy scraped images have a url from ingest time. User
    # uploads (see app/services/upload/) don't have one until the background
    # worker finishes processing and derives it from processed_key — see
    # image_processing_worker.py.
    url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    # --------------------------------------------------
    # FLAGS / SCORING
    # --------------------------------------------------

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
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
    # USER UPLOAD PIPELINE
    # --------------------------------------------------
    # These back app/services/upload/upload_service.py and
    # app/workers/image_processing_worker.py. Only populated for
    # user-submitted photos (place_id images ingested from Google Places
    # never set these — they use `url` directly instead).
    #
    # We never store full URLs for uploaded images (see key_builder.py) —
    # only R2 object keys. The worker derives `url` from processed_key once
    # processing succeeds, so existing url-based read paths (gallery query,
    # primary_image_url_subquery, etc.) keep working unchanged.

    orig_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    processed_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumb_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # pending -> processing -> ready | failed
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ready",
        server_default=text("'ready'"),
        index=True,
    )

    processing_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    phash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --------------------------------------------------
    # MODERATION (see app/services/images/upload_moderation.py)
    # --------------------------------------------------
    # Distinct from `status` above, which tracks the processing lifecycle
    # (pending/processing/ready/failed). An upload can process perfectly
    # and still be withheld from display. Scraped/legacy images default to
    # "approved" — they never went through user upload.
    moderation_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="approved",
        server_default="approved",
        index=True,
    )

    # Why it was rejected or held, e.g. "too_blurry", "safety_adult",
    # "unscanned_new_contributor", "user_reported".
    moderation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Variance of the Laplacian, measured on the ORIGINAL bytes before the
    # processing pipeline sharpens them. Kept raw (not just folded into
    # quality_score) so thresholds can be retuned against real data later
    # without re-downloading every image.
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # EXIF GPS placed this photo at the establishment it was uploaded to.
    # Corroboration of a real visit, never a requirement — most photos
    # legitimately carry no GPS at all.
    gps_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"),
    )

    # Whether SafeSearch actually ran. False means "not checked", which is
    # different from "checked and clean" — the moderation policy treats
    # them differently.
    safety_scanned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"),
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Supabase user id of the uploader. Nullable — legacy/scraped images have
    # no uploader. Not exposed on any public API response.
    uploaded_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

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