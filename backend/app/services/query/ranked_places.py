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


def get_ranked_places(
    db: Session,
    *,
    city_id: str,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Tuple[List[Place], int]:
    """
    Production-safe ranked places query.

    Guarantees
    ----------
    • filters by city
    • filters active places
    • optional category filter via join table
    • optional price tier filter
    • deterministic ordering
    • safe count under joins
    • SQLite/Postgres safe
    • read-only query
    """

    city_id = (city_id or "").strip()
    if not city_id:
        return [], 0

    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)

    # ---------------------------------------------------------
    # Base query
    # ---------------------------------------------------------

    stmt = select(Place).where(
        Place.city_id == city_id,
        Place.is_active.is_(True),
    )

    # ---------------------------------------------------------
    # Category filter
    # ---------------------------------------------------------

    if category_id:
        stmt = (
            stmt.join(
                place_categories,
                Place.id == place_categories.c.place_id,
            )
            .where(place_categories.c.category_id == category_id)
        )

    # ---------------------------------------------------------
    # Price filter
    # ---------------------------------------------------------

    if price_tier is not None:
        stmt = stmt.where(Place.price_tier == price_tier)

    # ---------------------------------------------------------
    # Prevent duplicates from joins
    # ---------------------------------------------------------

    stmt = stmt.distinct()

    # ---------------------------------------------------------
    # Safe count
    # ---------------------------------------------------------

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.execute(count_stmt).scalar_one()

    # ---------------------------------------------------------
    # Deterministic ordering
    # ---------------------------------------------------------

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