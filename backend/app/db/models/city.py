from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import String, Boolean, Index, text, inspect, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

# ---------------------------------------------------------
# DETERMINISTIC ID
# ---------------------------------------------------------

CITY_NAMESPACE = uuid.UUID("22334455-6677-8899-aabb-ccddeeff0011")


def city_uuid(slug: str) -> str:
    normalized = (slug or "").strip().lower()
    return str(uuid.uuid5(CITY_NAMESPACE, normalized))


# ---------------------------------------------------------
# MODEL
# ---------------------------------------------------------

class City(Base, TimestampMixin):
    __tablename__ = "cities"

    __table_args__ = (
        Index("ix_cities_slug", "slug"),
        Index("ix_cities_active", "is_active"),
        Index("ix_cities_geo", "lat", "lng"),
    )

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    country: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="US",
        server_default=text("'US'"),
    )

    lat: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    lng: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------

    places: Mapped[list["Place"]] = relationship(
        "Place",
        back_populates="city",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    # -----------------------------------------------------
    # INIT
    # -----------------------------------------------------

    def __init__(
        self,
        *,
        slug: str,
        name: str,
        state: Optional[str] = None,
        country: str = "US",
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        is_active: bool = True,
        id: Optional[str] = None,
    ):
        normalized_slug = (slug or "").strip().lower()
        normalized_name = (name or "").strip()

        if not normalized_slug:
            raise ValueError("City slug cannot be empty.")

        if not normalized_name:
            raise ValueError("City name cannot be empty.")

        self.slug = normalized_slug
        self.name = normalized_name
        self.state = state
        self.country = country or "US"

        self.lat = lat
        self.lng = lng

        self.is_active = bool(is_active)

        self.id = id or city_uuid(normalized_slug)

    # -----------------------------------------------------
    # IMMUTABILITY GUARD
    # -----------------------------------------------------

    def __setattr__(self, key, value):
        if key == "id":
            state = inspect(self)
            if state.persistent and getattr(self, "id", None) != value:
                raise AttributeError("City id is immutable once set.")
        super().__setattr__(key, value)