from __future__ import annotations

import uuid


from sqlalchemy import (
    String,
    Float,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place


class PlaceTruth(Base, TimestampMixin):
    """
    Canonical resolved truths for a Place.

    Guarantees:
    • One truth per (place_id, truth_type)
    • Deterministic resolver output
    • Auditable (resolved_from stored)
    • JSON-safe + cross-DB compatible
    """

    __tablename__ = "place_truths"

    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "truth_type",
            name="uq_place_truth_place_type",
        ),
        Index("ix_truth_place", "place_id"),
        Index("ix_truth_type", "truth_type"),
        Index("ix_truth_confidence", "confidence"),
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

    truth_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # VALUE
    # --------------------------------------------------

    truth_value: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
        index=True,
    )

    # --------------------------------------------------
    # AUDIT / TRACEABILITY
    # --------------------------------------------------

    resolved_from: Mapped[str | None] = mapped_column(
    String(512),
    nullable=True,
    )

    resolver_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="v2",
        server_default="v2",
    )

    # --------------------------------------------------
    # OPTIONAL STRUCTURED STORAGE (future-proof)
    # --------------------------------------------------

    sources_json: Mapped[dict | None] = mapped_column(
    JSON,
    nullable=True,
    )   

    # --------------------------------------------------
    # RELATIONSHIP
    # --------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        back_populates="truths",
        lazy="selectin",
        passive_deletes=True,
    )