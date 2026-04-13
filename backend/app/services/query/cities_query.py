from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.city import City


DEFAULT_LIMIT = 200
MAX_LIMIT = 500


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def get_cities(
    db: Session,
    *,
    limit: int = DEFAULT_LIMIT,
) -> List[City]:
    """
    Fetch active cities.

    Guarantees
    ----------
    • deterministic ordering
    • read-only query
    • SQLite/Postgres safe
    """

    limit = _clamp_limit(limit)

    return (
        db.query(City)
        .filter(City.is_active.is_(True))
        .order_by(
            City.name.asc(),
            City.id.asc(),
        )
        .limit(limit)
        .all()
    )


def get_city(
    db: Session,
    city_id: str,
) -> Optional[City]:
    """
    Fetch a single active city by ID.
    """

    city_id = (city_id or "").strip()
    if not city_id:
        return None

    return (
        db.query(City)
        .filter(
            City.id == city_id,
            City.is_active.is_(True),
        )
        .one_or_none()
    )


def get_city_by_slug(
    db: Session,
    slug: str,
) -> Optional[City]:
    """
    Fetch a single active city by slug.
    """

    slug = (slug or "").strip()
    if not slug:
        return None

    return (
        db.query(City)
        .filter(
            City.slug == slug,
            City.is_active.is_(True),
        )
        .one_or_none()
    )