from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import String, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import inspect

from app.db.models.base import Base, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.place import Place

# ---------------------------------------------------------
# DETERMINISTIC ID
# ---------------------------------------------------------

CATEGORY_NAMESPACE = uuid.UUID("87654321-4321-6789-4321-678987654321")


def category_uuid(slug: str) -> str:
    normalized = (slug or "").strip().lower()
    return str(uuid.uuid5(CATEGORY_NAMESPACE, f"category:{normalized}"))


# ---------------------------------------------------------
# ENUM
# ---------------------------------------------------------

class CategoryType(str, Enum):
    cuisine = "cuisine"
    venue = "venue"
    specialty = "specialty"


# ---------------------------------------------------------
# MODEL
# ---------------------------------------------------------

class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    slug: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
    )

    # -----------------------------------------------------
    # METADATA
    # -----------------------------------------------------

    icon: Mapped[str | None] = mapped_column(String(120))
    color: Mapped[str | None] = mapped_column(String(50))

    type: Mapped[CategoryType] = mapped_column(
        SQLEnum(
            CategoryType,
            name="category_type_enum",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        default=CategoryType.cuisine,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------

    places: Mapped[list["Place"]] = relationship(
        "Place",
        secondary="place_categories",
        back_populates="categories",
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
        type: CategoryType = CategoryType.cuisine,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        is_active: bool = True,
    ):
        normalized_slug = (slug or "").strip().lower()
        normalized_name = (name or "").strip()

        if not normalized_slug:
            raise ValueError("Category slug cannot be empty.")

        if not normalized_name:
            raise ValueError("Category name cannot be empty.")

        self.id = category_uuid(normalized_slug)
        self.slug = normalized_slug
        self.name = normalized_name

        self.type = type
        self.icon = icon
        self.color = color
        self.is_active = bool(is_active)

    # -----------------------------------------------------
    # IMMUTABILITY GUARD
    # -----------------------------------------------------

    def __setattr__(self, key, value):
        if key == "slug":
            state = inspect(self)
            if state.persistent and getattr(self, "slug", None) != value:
                raise AttributeError("Slug is immutable once set.")
        super().__setattr__(key, value)