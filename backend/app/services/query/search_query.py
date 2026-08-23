from __future__ import annotations

from typing import Optional, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy import case, select, func

from app.db.models.place import Place
from app.db.models.place_categories import place_categories


DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Sentinel "distance" for a place with no coordinates, so it still sorts
# after every real match instead of needing dialect-specific NULLS LAST
# handling (SQLite/Postgres both handle a plain numeric ORDER BY the
# same way).
_NO_COORDS_DISTANCE_SQ = 1e18


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
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
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
        Place.is_active.is_(True),
        Place.name.ilike(search_term),
    )

    if city_id:
        stmt = stmt.where(Place.city_id == city_id)

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

    # Without an explicit city scope, a name match is fetched from the
    # entire catalog ordered by rank_score alone — a real nearby match
    # with a modest rank_score can lose out to unrelated, higher-ranked
    # places in other cities and never even make it into this LIMIT
    # window, no matter how search_ranker.py re-sorts what *did* get
    # fetched. Ordering the fetch itself by proximity when the caller has
    # a location fixes that at the source: a true match near the caller
    # is now guaranteed a spot in the window regardless of how it
    # compares nationally, with rank_score only breaking ties among
    # similarly-distant results.
    if lat is not None and lng is not None:
        distance_sq = case(
            (Place.lat.is_(None), _NO_COORDS_DISTANCE_SQ),
            (Place.lng.is_(None), _NO_COORDS_DISTANCE_SQ),
            else_=(Place.lat - lat) * (Place.lat - lat) + (Place.lng - lng) * (Place.lng - lng),
        )
        order_by = (distance_sq.asc(), Place.rank_score.desc(), Place.id.asc())
    else:
        order_by = (Place.rank_score.desc(), Place.id.asc())

    stmt = stmt.order_by(*order_by).limit(limit).offset(offset)

    results = db.execute(stmt).scalars().all()

    return results, total_count