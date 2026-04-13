from __future__ import annotations

import uuid


from sqlalchemy import (
    String,
    Float,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

class PlaceClaim(Base, TimestampMixin):
    """
    Raw factual claims about a Place.

    Guarantees:
    • Supports multi-type values (text, number, json)
    • Deterministic dedupe per field + key
    • Safe scoring inputs for resolver
    • Fully cross-DB compatible
    """

    __tablename__ = "place_claims"

    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "field",
            "claim_key",
            name="uq_place_claim_place_field_key",
        ),
        Index("ix_claim_place_field", "place_id", "field"),
        Index("ix_claim_place_confidence", "place_id", "confidence"),

        # 🔥 PROTECTION: ensure at least ONE value exists
        CheckConstraint(
            "(value_text IS NOT NULL) OR (value_number IS NOT NULL) OR (value_json IS NOT NULL)",
            name="ck_place_claim_has_value",
        ),
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

    field: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    claim_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
        server_default=text("''"),
        index=True,
    )

    # --------------------------------------------------
    # VALUE TYPES
    # --------------------------------------------------

    value_text: Mapped[str | None] = mapped_column(
    String,
    nullable=True,
    )

    value_number: Mapped[float | None] = mapped_column(
    Float,
    nullable=True,
    )

    value_json: Mapped[dict | None] = mapped_column(
    JSON,
    nullable=True,
    )

    # --------------------------------------------------
    # SCORING INPUTS
    # --------------------------------------------------

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        server_default=text("0.5"),
        index=True,
    )

    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default=text("1.0"),
    )

    source: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    is_verified_source: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    is_user_submitted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    # --------------------------------------------------
    # RELATIONSHIP
    # --------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        back_populates="claims",
        lazy="selectin",
        passive_deletes=True,
    )