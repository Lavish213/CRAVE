from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.city import City
    from app.db.models.place import Place

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CityPlaceRanking(Base):
    """
    FINALIZED PRODUCTION RANKING SNAPSHOT

    Guarantees:
    - Deterministic ordering per city
    - Fast feed queries
    - Stable pagination
    - Safe for recompute + overwrite cycles

    Notes:
    - This is NOT append-only
    - Ranking worker replaces rows per city
    """

    __tablename__ = "city_place_rankings"

    __table_args__ = (
        # Prevent duplicate place per city
        UniqueConstraint(
            "city_id",
            "place_id",
            name="uq_city_place_ranking_city_place",
        ),

        # 🔥 FEED QUERY (top N per city)
        Index(
            "ix_city_place_rankings_city_rank",
            "city_id",
            "rank_position",
        ),

        # 🔥 SORT BY SCORE
        Index(
            "ix_city_place_rankings_score",
            "city_id",
            "rank_score",
        ),

        # 🔥 REBUILD / DEBUG
        Index(
            "ix_city_place_rankings_created",
            "created_at",
        ),
    )

    # --------------------------------------------------
    # IDENTITY
    # --------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    city_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # RANK DATA
    # --------------------------------------------------

    rank_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    rank_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
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
    # RELATIONSHIPS
    # --------------------------------------------------

    city: Mapped["City"] = relationship(
        "City",
        lazy="joined",
    )

    place: Mapped["Place"] = relationship(
        "Place",
        lazy="joined",
    )