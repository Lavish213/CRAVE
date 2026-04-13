from __future__ import annotations

from typing import Optional, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.models.place import Place
from app.db.models.place_categories import place_categories


DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _clamp_offset(offset: int) -> int:
    try:
        n = int(offset)
    except Exception:
        return 0
    return max(0, n)


def search_places(
    db: Session,
    *,
    query: str,
    city_id: str,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Tuple[List[Place], int]:

    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)

    query = (query or "").strip()

    if not query:
        return [], 0

    search_term = f"%{query}%"

    stmt = select(Place).where(
        Place.city_id == city_id,
        Place.is_active.is_(True),
        Place.name.ilike(search_term),
    )

    if category_id:
        stmt = (
            stmt.join(
                place_categories,
                Place.id == place_categories.c.place_id,
            )
            .where(place_categories.c.category_id == category_id)
        )

    if price_tier is not None:
        stmt = stmt.where(Place.price_tier == price_tier)

    stmt = stmt.distinct()

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.execute(count_stmt).scalar_one()

    stmt = (
        stmt.order_by(
            Place.rank_score.desc(),
            Place.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    results = db.execute(stmt).scalars().all()

    return results, total_count