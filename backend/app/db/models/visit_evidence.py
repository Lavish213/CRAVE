from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

VISIT_TIER_DECLARED = "declared"
VISIT_TIER_VERIFIED = "verified"
VISIT_TIER_INFERRED = "inferred"
VALID_VISIT_TIERS = {
    VISIT_TIER_DECLARED,
    VISIT_TIER_VERIFIED,
    VISIT_TIER_INFERRED,
}


class VisitEvidence(Base, TimestampMixin):
    """
    Factual evidence that a user experienced a place.

    This record deliberately does not encode whether the user liked the place.
    Preference lives in separate taste evidence. `factual_history` and
    `recommendation_influence` are independent so a user can exclude an event
    from personalization without rewriting the historical fact.
    """

    __tablename__ = "visit_evidence"
    __table_args__ = (
        CheckConstraint(
            "tier in ('declared', 'verified', 'inferred')",
            name="visit_evidence_valid_tier",
        ),
        Index("ix_visit_evidence_user_tier_occurred", "user_id", "tier", "occurred_at"),
        Index("ix_visit_evidence_user_place", "user_id", "place_id"),
        Index("ix_visit_evidence_source_ref", "source", "source_ref"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    place_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="CASCADE"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    factual_history: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    recommendation_influence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
