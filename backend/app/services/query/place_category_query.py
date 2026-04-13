from __future__ import annotations

import logging
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.category import Category
from app.db.models.place_categories import place_categories


logger = logging.getLogger(__name__)


def get_categories_for_place(
    db: Session,
    *,
    place_id: str,
) -> List[Category]:
    """
    Single place category fetch.

    Guarantees:
    • safe input handling
    • deterministic ordering
    • never crashes
    """

    place_id = (place_id or "").strip()
    if not place_id:
        return []

    try:
        stmt = (
            select(Category)
            .join(
                place_categories,
                place_categories.c.category_id == Category.id,
            )
            .where(
                place_categories.c.place_id == place_id,
            )
            .order_by(
                Category.name.asc(),
                Category.id.asc(),
            )
        )

        return db.execute(stmt).scalars().all() or []

    except Exception as exc:
        logger.exception(
            "get_categories_for_place_failed place_id=%s error=%s",
            place_id,
            exc,
        )
        return []


def get_categories_for_places_bulk(
    db: Session,
    *,
    place_ids: List[str],
) -> Dict[str, List[Category]]:
    """
    Bulk category fetch.

    Guarantees:
    • single query (no N+1)
    • deterministic grouping
    • safe fallback
    • deduped per place
    """

    if not place_ids:
        return {}

    try:
        stmt = (
            select(
                place_categories.c.place_id,
                Category,
            )
            .join(
                Category,
                place_categories.c.category_id == Category.id,
            )
            .where(
                place_categories.c.place_id.in_(place_ids),
            )
            .order_by(
                place_categories.c.place_id.asc(),
                Category.name.asc(),
                Category.id.asc(),
            )
        )

        rows = db.execute(stmt).all()

        grouped: Dict[str, List[Category]] = {}
        seen: Dict[str, set[str]] = {}

        for place_id, category in rows:
            if not place_id or not category:
                continue

            cat_id = getattr(category, "id", None)
            if not cat_id:
                continue

            if place_id not in grouped:
                grouped[place_id] = []
                seen[place_id] = set()

            if cat_id in seen[place_id]:
                continue

            seen[place_id].add(cat_id)
            grouped[place_id].append(category)

        return grouped

    except Exception as exc:
        logger.exception(
            "get_categories_for_places_bulk_failed count=%s error=%s",
            len(place_ids),
            exc,
        )
        return {}