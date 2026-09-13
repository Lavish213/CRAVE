from __future__ import annotations

from typing import Optional, Tuple, List, Sequence

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_truth import PlaceTruth
from app.services.query.search_query import MAX_CANDIDATE_POOL, search_places
from app.services.search.search_ranker import rank_search_results
from app.services.spatial.geohash_utils import haversine_distance_km

_KM_TO_MILES = 0.621371

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
    radius_miles: Optional[float] = None,
    limit: int = 20,
    offset: int = 0,
    required_category_names: Sequence[str] = (),
    required_amenities: Sequence[str] = (),
) -> Tuple[List[Place], int]:
    """
    Execute a place search and apply post-query ranking.

    When lat/lng provided, proximity is incorporated into ranking so
    nearby relevant results surface above distant ones of equal quality.
    When radius_miles is also provided, results beyond it are excluded
    entirely (not just ranked lower) -- an exact haversine cut over the
    already-fetched candidate pool, not a second SQL round-trip. A place
    with no coordinates can't satisfy a radius request and is excluded,
    same as it already sorts last for plain proximity ranking.

    total_count reflects the radius-filtered count when radius_miles is
    set, bounded by the same candidate pool every other caller of this
    function already accepts (MAX_CANDIDATE_POOL) -- a true total beyond
    that pool was already an accepted approximation here before radius
    filtering existed (see _RANK_POOL_PADDING's own comment above).

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
        required_category_names=required_category_names,
    )

    if radius_miles is not None and lat is not None and lng is not None:
        candidates = [
            place for place in candidates
            if place.lat is not None and place.lng is not None
            and haversine_distance_km(lat, lng, place.lat, place.lng) * _KM_TO_MILES <= radius_miles
        ]
        total = len(candidates)

    # Amenity requirements (outdoor seating, ...) are enforced the same as a
    # dietary hard constraint -- never auto-relaxed. outdoor_seating isn't a
    # plain Place column -- it's a resolved PlaceTruth row (truth_value one
    # of "yes"/"no"/"limited", written by promote_service_v2.py's OSM-claim
    # pipeline; see place_detail_router.py's identical read). One bulk query
    # over the already-fetched candidate pool, same reasoning as radius_miles
    # above: a post-filter, not a second round-trip per place. Only "yes"
    # satisfies a required amenity -- "limited" is a real but partial answer
    # a user who typed "patio required" almost certainly didn't mean, and
    # "no" or no row at all both fail it, same as ranking's own missing-data
    # standing everywhere else in this file (missing is not negative
    # evidence, but it's also not the confirmed "yes" a hard requirement
    # needs).
    if "outdoor_seating" in required_amenities:
        candidate_ids = [place.id for place in candidates]
        confirmed_ids = {
            row.place_id
            for row in db.query(PlaceTruth.place_id).filter(
                PlaceTruth.place_id.in_(candidate_ids),
                PlaceTruth.truth_type == "outdoor_seating",
                PlaceTruth.truth_value == "yes",
            )
        } if candidate_ids else set()
        candidates = [place for place in candidates if place.id in confirmed_ids]
        total = len(candidates)

    ranked = rank_search_results(list(candidates), query=query, lat=lat, lng=lng)
    page = ranked[offset:offset + limit]

    return page, total
