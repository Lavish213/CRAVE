from __future__ import annotations

import uuid
from typing import Dict, Any

from sqlalchemy import (
    String,
    Float,
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
            "name",
            "category",
            name="uq_menu_place_name_category",
        ),
        Index("ix_menu_place", "place_id"),
        Index("ix_menu_place_created", "place_id", "created_at"),
        Index("ix_menu_category", "category"),
        Index("ix_menu_price", "price"),
        Index("ix_menu_active", "is_active"),
        Index("ix_menu_snapshot", "source_snapshot_id"),
        Index("ix_menu_place_active", "place_id", "is_active"),
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

    price: Mapped[float | None] = mapped_column(
        Float,
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
        category: str | None = None,
        price: float | None = None,
        description: str | None = None,
        image: str | None = None,
        raw_payload: Dict[str, Any] | None = None,
        source_snapshot_id: str | None = None,
    ):
        normalized_name = (name or "").strip()

        if not normalized_name:
            raise ValueError("MenuItem name cannot be empty.")

        self.place_id = place_id
        self.name = normalized_name
        self.category = (category or "").strip() or None

        try:
            self.price = round(float(price), 2) if price is not None else None
        except Exception:
            self.price = None

        self.description = (description or "").strip() or None
        self.image = image
        self.raw_payload = raw_payload
        self.source_snapshot_id = source_snapshot_id