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
            # rank_position is 1-indexed, 1 = best. This assumes
            # rank_position always falls within [1, total] for its own
            # city -- true immediately after city_ranking_worker.py's
            # recompute_city_ranking() runs (it deletes and reinserts a
            # city's entire snapshot in one transaction, positions 1..N
            # matching that same N). Confirmed in production it can
            # still drift out of that range regardless (a stale
            # rank_position surviving from before some of that city's
            # rows were pruned some other way) -- and PlaceCardOut/
            # PlaceOut both hard-require rank_percentile in [0.0, 1.0],
            # so an out-of-range value here doesn't just mean a wrong
            # badge, it throws inside Pydantic validation and silently
            # drops that place from every caller's response entirely
            # (confirmed: this was making /search return items=[] with
            # a correct total for every query, and is the likely
            # explanation for at least part of the similar Feed
            # under-counting bug logged in places.py). Clamping here
            # means a data problem in city_place_rankings degrades to
            # "this place's tier badge is a bit off" instead of
            # "this place vanishes from search/feed results entirely".
            raw = 1.0 - (rank_position - 1) / (total - 1)
            percentiles[place_id] = max(0.0, min(1.0, raw))

    return percentiles
