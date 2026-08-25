from __future__ import annotations

from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.city_place_ranking import CityPlaceRanking


def get_rank_percentiles(db: Session, *, place_ids: List[str]) -> Dict[str, float]:
    """
    Bulk-look-up each place's standing within its own city, as a percentile
    in [0.0, 1.0] where 1.0 = best place in the city and 0.0 = worst.

    Backed by CityPlaceRanking, a deterministic per-city snapshot
    (city_place_ranking_worker, scheduled hourly via app/scheduler.py's
    "ranking_update" job) rather than a live query, so this stays fast and
    consistent within a request.

    A place absent from the returned dict has no ranking snapshot yet
    (e.g. added since the last hourly run, or in a city with zero other
    ranked places) -- callers must treat that as "unknown", not "worst",
    and fall back to whatever legacy behavior makes sense for them.
    """
    if not place_ids:
        return {}

    city_total = (
        func.count()
        .over(partition_by=CityPlaceRanking.city_id)
        .label("city_total")
    )

    stmt = select(
        CityPlaceRanking.place_id,
        CityPlaceRanking.rank_position,
        city_total,
    ).where(CityPlaceRanking.place_id.in_(place_ids))

    percentiles: Dict[str, float] = {}
    for place_id, rank_position, total in db.execute(stmt).all():
        if total <= 1:
            percentiles[place_id] = 1.0
        else:
            # rank_position is 1-indexed, 1 = best.
            percentiles[place_id] = 1.0 - (rank_position - 1) / (total - 1)

    return percentiles
