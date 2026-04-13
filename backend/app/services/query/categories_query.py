from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.category import Category


DEFAULT_LIMIT = 200
MAX_LIMIT = 500


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


# =========================================================
# Category List
# =========================================================

def get_categories(
    db: Session,
    *,
    limit: int = DEFAULT_LIMIT,
) -> List[Category]:
    """
    Fetch active categories.

    Guarantees
    ----------
    • deterministic ordering
    • read-only query
    • SQLite/Postgres safe
    """

    limit = _clamp_limit(limit)

    return (
        db.query(Category)
        .filter(Category.is_active.is_(True))
        .order_by(
            Category.name.asc(),
            Category.id.asc(),
        )
        .limit(limit)
        .all()
    )


# =========================================================
# Single Category by ID
# =========================================================

def get_category(
    db: Session,
    category_id: str,
) -> Optional[Category]:
    """
    Fetch a single active category by ID.
    """

    category_id = (category_id or "").strip()
    if not category_id:
        return None

    return (
        db.query(Category)
        .filter(
            Category.id == category_id,
            Category.is_active.is_(True),
        )
        .one_or_none()
    )


# =========================================================
# Single Category by Slug
# =========================================================

def get_category_by_slug(
    db: Session,
    slug: str,
) -> Optional[Category]:
    """
    Fetch a single active category by slug.
    """

    slug = (slug or "").strip()
    if not slug:
        return None

    return (
        db.query(Category)
        .filter(
            Category.slug == slug,
            Category.is_active.is_(True),
        )
        .one_or_none()
    )