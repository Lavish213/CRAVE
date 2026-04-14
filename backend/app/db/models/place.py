from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin
from app.db.models.place_categories import place_categories

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.city import City
    from app.db.models.category import Category
    from app.db.models.place_claim import PlaceClaim
    from app.db.models.place_truth import PlaceTruth
    from app.db.models.place_image import PlaceImage
    from app.db.models.place_feed_snapshot import PlaceFeedSnapshot

PLACE_NAMESPACE = uuid.UUID("11223344-5566-7788-99aa-bbccddeeff00")


def place_uuid(name: str, city_id: str) -> str:
    normalized_name = (name or "").strip().lower()
    normalized_city_id = (city_id or "").strip()
    return str(uuid.uuid5(PLACE_NAMESPACE, f"{normalized_city_id}:{normalized_name}"))


class Place(Base, TimestampMixin):
    __tablename__ = "places"

    __table_args__ = (
        UniqueConstraint("city_id", "name", name="uq_places_city_name"),
        Index("ix_places_city_rank_id", "city_id", "rank_score", "id"),
        Index("ix_places_city_active", "city_id", "is_active"),
        Index("ix_places_geo", "lat", "lng"),
        Index("ix_places_price_tier", "price_tier"),
        Index("ix_places_created_at", "created_at"),
        Index("ix_places_website", "website"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    city_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        index=True,
    )

    grubhub_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        index=True,
    )

    menu_source_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    lat: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    price_tier: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    master_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
        index=True,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )

    operational_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )

    local_validation: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )

    hype_penalty: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )

    rank_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
        index=True,
    )

    # ✅ FIXED: properly indented
    has_menu: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )

    last_menu_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    score_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    last_scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    needs_recompute: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
    )

    image_fetch_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    image_blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )

    city: Mapped["City"] = relationship(
        "City",
        back_populates="places",
        lazy="selectin",
    )

    categories: Mapped[list["Category"]] = relationship(
        "Category",
        secondary=place_categories,
        back_populates="places",
        passive_deletes=True,
        lazy="selectin",
    )

    claims: Mapped[list["PlaceClaim"]] = relationship(
        "PlaceClaim",
        back_populates="place",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    truths: Mapped[list["PlaceTruth"]] = relationship(
        "PlaceTruth",
        back_populates="place",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    images: Mapped[list["PlaceImage"]] = relationship(
        "PlaceImage",
        back_populates="place",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    feed_snapshots: Mapped[list["PlaceFeedSnapshot"]] = relationship(
        "PlaceFeedSnapshot",
        back_populates="place",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __init__(
        self,
        *,
        name: str,
        city_id: str,
        lat: float | None = None,
        lng: float | None = None,
        price_tier: int | None = None,
        is_active: bool = True,
        website: str | None = None,
        id: str | None = None,
        confidence_score: float = 0.0,
        operational_confidence: float = 0.0,
        local_validation: float = 0.0,
        hype_penalty: float = 0.0,
        master_score: float = 0.0,
        rank_score: float = 0.0,
    ):
        normalized_name = (name or "").strip()
        normalized_city_id = (city_id or "").strip()

        if not normalized_name:
            raise ValueError("Place name cannot be empty.")

        if not normalized_city_id:
            raise ValueError("Place city_id cannot be empty.")

        self.name = normalized_name
        self.city_id = normalized_city_id

        self.id = id or place_uuid(normalized_name, normalized_city_id)

        self.website = (website or "").strip().lower() or None

        try:
            self.lat = float(lat) if lat is not None else None
        except Exception:
            self.lat = None

        try:
            self.lng = float(lng) if lng is not None else None
        except Exception:
            self.lng = None

        try:
            self.price_tier = int(price_tier) if price_tier is not None else None
        except Exception:
            self.price_tier = None

        self.is_active = bool(is_active)

        self.confidence_score = float(confidence_score or 0.0)
        self.operational_confidence = float(operational_confidence or 0.0)
        self.local_validation = float(local_validation or 0.0)
        self.hype_penalty = float(hype_penalty or 0.0)
        self.master_score = float(master_score or 0.0)
        self.rank_score = float(rank_score or 0.0)

    def __setattr__(self, key, value):
        if key in {"id", "city_id"}:
            state = inspect(self)
            if state.persistent and getattr(self, key, None) != value:
                raise AttributeError(f"{key} is immutable once set.")
        super().__setattr__(key, value)