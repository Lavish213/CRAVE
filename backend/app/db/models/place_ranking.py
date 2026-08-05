# app/db/models/place_ranking.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

# The three buckets a user picks when logging a visit, before any pairwise
# comparison happens — reverse-engineered from how Beli's own flow works
# ("I liked it!" / "It was fine" / "I didn't like it"). Score bands below
# are this app's own convention, not Beli's literal internal formula.
TIER_LIKED = "liked"
TIER_FINE = "fine"
TIER_DISLIKED = "disliked"
VALID_TIERS = {TIER_LIKED, TIER_FINE, TIER_DISLIKED}

# Inclusive [floor, ceiling] a tier's interpolated rank_score is confined to.
# A comparison never crosses a tier boundary — "fine" can never outscore
# "liked", no matter how the pairwise comparisons land within each tier.
TIER_SCORE_BANDS = {
    TIER_DISLIKED: (0.0, 3.3),
    TIER_FINE: (3.3, 6.6),
    TIER_LIKED: (6.6, 10.0),
}


class PlaceRanking(Base, TimestampMixin):
    """
    A user's personal, comparison-derived ranking of a place they've
    visited — see app.services.ranking.ranking_service for the actual
    binary-insertion algorithm that produces rank_score.
    """

    __tablename__ = "place_rankings"

    __table_args__ = (
        UniqueConstraint("user_id", "place_id", name="uq_place_rankings_user_place"),
        # `alembic check`/autogenerate always reports this as drift (wanting
        # ck_place_rankings_ck_place_rankings_valid_tier — the "ck" naming
        # convention gets applied on top of this explicit name, doubling
        # the prefix). The real deployed constraint is this exact name;
        # renaming it would need a migration for a purely cosmetic change,
        # same known/harmless situation as categories.category_type_enum in
        # app/db/models/category.py.
        CheckConstraint(
            "tier in ('liked', 'fine', 'disliked')", name="ck_place_rankings_valid_tier"
        ),
        Index("ix_place_rankings_user_tier_score", "user_id", "tier", "rank_score"),
        Index("ix_place_rankings_place_id", "place_id"),
        # Explicit name — index=True here would route through Base's naming
        # convention and mismatch what the migration actually deployed (see
        # NAMING_CONVENTION's comment in app/db/models/base.py).
        Index("ix_place_rankings_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)

    place_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="CASCADE"), nullable=False
    )

    tier: Mapped[str] = mapped_column(String(16), nullable=False)

    # Position within (user_id, tier), interpolated to a 0-10 display score
    # by the ranking service. Fractional/"insert between neighbors" by
    # design — inserting one new ranking never requires renumbering
    # everyone else's.
    rank_score: Mapped[float] = mapped_column(Float, nullable=False)

    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
