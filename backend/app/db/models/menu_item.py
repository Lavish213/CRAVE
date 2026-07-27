from __future__ import annotations

import uuid
from typing import Dict, Any

from sqlalchemy import (
    String,
    Float,
    Integer,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
    Boolean,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"

    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "fingerprint",
            name="uq_menu_place_fingerprint",
        ),
        Index("ix_menu_place", "place_id"),
        Index("ix_menu_place_created", "place_id", "created_at"),
        Index("ix_menu_category", "category"),
        Index("ix_menu_price_cents", "price_cents"),
        Index("ix_menu_active", "is_active"),
        Index("ix_menu_snapshot", "source_snapshot_id"),
        Index("ix_menu_place_active", "place_id", "is_active"),
        Index("ix_menu_provider", "provider"),
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

    # --------------------------------------------------
    # CORE DATA
    # --------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    # price_cents: canonical integer cents (e.g. 1299 = $12.99). NULL = price unknown.
    # NEVER store float dollars. NEVER store raw cents as float.
    price_cents: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    image: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # --------------------------------------------------
    # FINGERPRINT (dedup backbone)
    # SHA256 of normalized(name|section|currency) — price excluded intentionally
    # so price changes don't create duplicates.
    # --------------------------------------------------

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # CONFIDENCE + LINEAGE
    # --------------------------------------------------

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )

    provider: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    source_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    # --------------------------------------------------
    # SOURCE / TRACE
    # --------------------------------------------------

    raw_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    source_snapshot_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    # --------------------------------------------------
    # RELATIONSHIP
    # --------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        lazy="selectin",
        passive_deletes=True,
    )

    # --------------------------------------------------
    # INIT
    # --------------------------------------------------

    def __init__(
        self,
        *,
        place_id: str,
        name: str,
        fingerprint: str,
        category: str | None = None,
        price_cents: int | None = None,
        description: str | None = None,
        image: str | None = None,
        confidence_score: float = 0.0,
        provider: str | None = None,
        source_type: str | None = None,
        raw_payload: Dict[str, Any] | None = None,
        source_snapshot_id: str | None = None,
    ):
        normalized_name = (name or "").strip()

        if not normalized_name:
            raise ValueError("MenuItem name cannot be empty.")

        if not fingerprint:
            raise ValueError("MenuItem fingerprint cannot be empty.")

        self.place_id = place_id
        self.name = normalized_name
        self.fingerprint = fingerprint
        self.category = (category or "").strip() or None

        # Strict integer cents — reject floats at the boundary
        if price_cents is not None:
            if not isinstance(price_cents, int):
                raise TypeError(
                    f"price_cents must be int, got {type(price_cents).__name__}: {price_cents!r}"
                )
            if price_cents < 0:
                raise ValueError(f"price_cents cannot be negative: {price_cents}")
        self.price_cents = price_cents

        self.description = (description or "").strip() or None
        self.image = image
        self.confidence_score = float(confidence_score or 0.0)
        self.provider = (provider or "").strip() or None
        self.source_type = (source_type or "").strip() or None
        self.raw_payload = raw_payload
        self.source_snapshot_id = source_snapshot_id