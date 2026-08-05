from __future__ import annotations

import uuid
from datetime import datetime


from sqlalchemy import (
    String,
    Float,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    JSON,
    DateTime,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class DiscoveryCandidate(Base, TimestampMixin):

    __tablename__ = "discovery_candidates"

    __table_args__ = (
        UniqueConstraint(
            "city_id",
            "name",
            "lat",
            "lng",
            name="uq_candidate_city_name_location",
        ),
        UniqueConstraint(
            "external_id",
            "source",
            name="uq_candidate_external_source",
        ),
        Index("ix_candidate_city", "city_id"),
        Index("ix_candidate_status", "status"),
        Index("ix_candidate_confidence", "confidence_score"),
        Index("ix_candidate_category", "category_id"),
        Index("ix_candidate_external_id", "external_id"),
        Index("ix_candidate_source", "source"),
        Index("ix_candidate_lat", "lat"),
        Index("ix_candidate_lng", "lng"),
        Index("ix_candidate_promote", "confidence_score", "status"),
        Index("ix_candidate_resolved", "resolved", "blocked"),
        # Explicit name — index=True on next_retry_at below would route
        # through Base's naming convention and mismatch what's actually
        # deployed (see NAMING_CONVENTION's comment in app/db/models/base.py).
        Index("ix_candidate_next_retry_at", "next_retry_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    external_id: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    source: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        index=True,
    )

    city_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    category_hint: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="candidate",
        server_default="candidate",
        index=True,
    )

    resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    resolved_place_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    # 🔥 CRITICAL FIX (this was broken)
    promoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # 🔥 FIX (Dict[str, Any] → dict)
    raw_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Failure tracking (was entirely absent — promotion failures were
    # caught, rolled back, and silently discarded with no record. A
    # permanently-broken candidate would be retried every scheduler cycle
    # forever with no visibility that it was stuck. See
    # app.services.discovery.promotion_orchestrator_v2.)
    # ------------------------------------------------------------------

    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )

    last_error: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Corroboration tracking (see candidate_store_v2.upsert_discovery_candidate_v2)
    #
    # Distinct "someone/something independently vouched for this place"
    # signal keys (e.g. "user_gps:<user_id>", "user_share:<crave_item_id>").
    # Each *new* key seen accumulates confidence_score instead of the merge
    # just taking the max of old vs new — without this, the same person
    # re-confirming the same spot (or a second, third, fourth distinct
    # person doing so) could never add up toward the promotion threshold.
    # None/empty for candidates that only ever came from a single
    # authoritative automated source (OSM, Google Places, health dept),
    # which correctly still merge via max — a re-scan isn't new evidence.
    # ------------------------------------------------------------------

    corroboration_keys: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )