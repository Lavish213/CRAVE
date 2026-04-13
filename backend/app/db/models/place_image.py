from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

class PlaceImage(Base, TimestampMixin):
    __tablename__ = "place_images"

    __table_args__ = (
        # 🔥 enforce unique image per place
        Index("uq_place_image_place_url", "place_id", "url", unique=True),

        Index("ix_place_images_place_primary", "place_id", "is_primary"),
        Index("ix_place_images_confidence", "confidence"),
        Index("ix_place_images_created", "created_at"),
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
    # RELATIONSHIP
    # --------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        back_populates="images",
        lazy="selectin",
        passive_deletes=True,
    )