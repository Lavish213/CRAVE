from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place import Place


logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def build_search_index(db: Session) -> int:
    """
    Rebuild the in-process search index from active places.

    For Phase 1 this validates that all active places are queryable
    and returns the count of indexed places. Full-text or inverted-index
    structures can be layered in here without changing callers.

    Returns the number of places indexed.
    """

    stmt = (
        select(Place)
        .where(Place.is_active.is_(True))
        .order_by(Place.id.asc())
    )

    indexed = 0
    offset = 0

    while True:
        batch = db.execute(
            stmt.limit(BATCH_SIZE).offset(offset)
        ).scalars().all()

        if not batch:
            break

        for place in batch:
            if not place.name or not place.city_id:
                continue
            indexed += 1

        offset += BATCH_SIZE

        if len(batch) < BATCH_SIZE:
            break

    logger.debug("search_index_built count=%s", indexed)
    return indexed
