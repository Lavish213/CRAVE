from __future__ import annotations

from sqlalchemy import Table, Column, String, ForeignKey, Index
from app.db.models.base import Base


place_categories = Table(
    "place_categories",
    Base.metadata,

    Column(
        "place_id",
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),

    Column(
        "category_id",
        String(36),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)

# ---------------------------------------------------------
# INDEXES (EXPLICIT FOR PERFORMANCE)
# ---------------------------------------------------------

Index(
    "ix_place_categories_place",
    place_categories.c.place_id,
)

Index(
    "ix_place_categories_category",
    place_categories.c.category_id,
)

__all__ = ["place_categories"]