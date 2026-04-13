from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models.city import City


def list_cities(db: Session) -> List[City]:
    """
    Returns all active cities.

    Guarantees:
    - Deterministic ordering
    - Read-only
    - SQLite/Postgres safe
    """

    stmt = (
        select(City)
        .where(City.is_active.is_(True))
        .order_by(
            City.name.asc(),
            City.id.asc(),
        )
    )

    return db.execute(stmt).scalars().all()