from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models.category import Category


def get_categories(db: Session) -> List[Category]:
    """
    Returns all active categories.

    Guarantees:
    - Deterministic ordering
    - Read-only
    - SQLite/Postgres safe
    """

    stmt = (
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(
            Category.name.asc(),
            Category.id.asc(),
        )
    )

    return db.execute(stmt).scalars().all()


# Alias for backward compatibility
list_categories = get_categories