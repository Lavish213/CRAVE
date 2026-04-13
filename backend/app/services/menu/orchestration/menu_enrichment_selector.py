from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.place import Place


STALE_DAYS = 7


def get_places_needing_menus(
    db: Session,
    limit: int = 50,
) -> List[Place]:
    """
    Returns places that need menu enrichment.

    Conditions:
    - has_menu is False
    - last_menu_updated_at is NULL
    - or last_menu_updated_at is older than the stale cutoff
    """

    cutoff = datetime.now(UTC) - timedelta(days=STALE_DAYS)

    return (
        db.query(Place)
        .filter(
            Place.has_menu.is_(False),
            or_(
                Place.last_menu_updated_at.is_(None),
                Place.last_menu_updated_at < cutoff,
            ),
        )
        .limit(limit)
        .all()
    )