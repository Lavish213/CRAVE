from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.query.feed_mixer import mix_feed
from app.services.query.places_query import list_places
from app.services.query.discovery_places import list_discovery_places


logger = logging.getLogger("lavish.feed_worker")


DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT

    return max(1, min(MAX_LIMIT, n))


# =========================================================
# Feed Refresh Worker
# =========================================================

def refresh_feed(
    db: Session,
    *,
    city_id: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
) -> List[Place]:
    """
    Worker-safe feed refresh.

    Used for:
    • background feed warming
    • scheduled ranking refresh
    • testing feed pipeline outside API layer

    Guarantees
    ----------
    • deterministic ordering
    • stable discovery mixing
    • safe DB reads
    """

    limit = _clamp_limit(limit)

    logger.info(
        "feed_refresh_start city=%s limit=%s",
        city_id,
        limit,
    )

    # -----------------------------------------------------
    # Stable ranked places
    # -----------------------------------------------------

    stable = list_places(
        db=db,
        city_id=city_id,
        limit=limit * 2,
    )

    # -----------------------------------------------------
    # Discovery places
    # -----------------------------------------------------

    discovery = list_discovery_places(
        db=db,
        city_id=city_id,
        limit=limit,
    )

    # -----------------------------------------------------
    # Feed mixing
    # -----------------------------------------------------

    feed = mix_feed(
        stable_places=stable,
        discovery_places=discovery,
        limit=limit,
    )

    logger.info(
        "feed_refresh_complete city=%s returned=%s",
        city_id,
        len(feed),
    )

    return feed