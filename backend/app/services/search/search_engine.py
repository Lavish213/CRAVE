from __future__ import annotations

from typing import Optional, Tuple, List

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.query.search_query import MAX_CANDIDATE_POOL, search_places
from app.services.search.search_ranker import rank_search_results

# rank_search_results() re-scores with exact-match/menu/proximity boosts
# that search_query.py's raw SQL ORDER BY (rank_score/distance only) can't
# express. Fetching just this page's own narrow slice and re-ranking only
# that slice meant a result which would win *after* enrichment could never
# surface at all if it didn't already make the raw-ordered page window --
# pagination was cutting before ranking, not after it. Fetching a wider
# candidate pool, ranking that whole pool, and slicing the real page out
# of the ranked result fixes this for any page whose true contents fall
# within the pool. Bounded (MAX_CANDIDATE_POOL, shared with search_query.
# py's own fuzzy-fallback pool) for the same reason: unbounded regardless
# of result-set size would be unacceptable, and paging this deep into
# search results is not a realistic session for a real user.
#
# Passed to search_places() as its max_limit= override -- MAX_LIMIT (100)
# there is the honest public per-page cap; this pool is strictly
# internal, and this is the only caller allowed to ask for more than
# MAX_LIMIT. Confirmed real bug from an earlier version of this fix:
# without that override, search_places()'s own _clamp_limit(limit)
# silently truncated pool_limit back down to MAX_LIMIT, so any page with
# offset >= 100 sliced into a candidate list shorter than the requested
# offset and returned an empty page while total_count still reported
# real matches.
_RANK_POOL_PADDING = 100


def execute_search(
    db: Session,
    *,
    query: str,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Place], int]:
    """
    Execute a place search and apply post-query ranking.

    When lat/lng provided, proximity is incorporated into ranking so
    nearby relevant results surface above distant ones of equal quality.

    Returns (places, total_count).
    """

    pool_limit = min(MAX_CANDIDATE_POOL, offset + limit + _RANK_POOL_PADDING)

    candidates, total = search_places(
        db,
        query=query,
        city_id=city_id,
        category_id=category_id,
        price_tier=price_tier,
        lat=lat,
        lng=lng,
        limit=pool_limit,
        offset=0,
        max_limit=MAX_CANDIDATE_POOL,
    )

    ranked = rank_search_results(list(candidates), query=query, lat=lat, lng=lng)
    page = ranked[offset:offset + limit]

    return page, total
