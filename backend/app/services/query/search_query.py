from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy import case, exists, or_, select, func

from app.db.models.category import Category
from app.db.models.place import Place
from app.db.models.place_categories import place_categories


DEFAULT_LIMIT = 20
MAX_LIMIT = 100  # public per-page cap -- the route's own page_size validation enforces this too

# Separate, higher ceiling for execute_search()'s internal candidate-pool
# fetch (search_engine.py) -- NOT the same thing as MAX_LIMIT above. Post-
# query ranking there needs more raw-ordered candidates than one page's
# worth so it has room to promote a result into the requested page; this
# is the only caller allowed to ask for more than MAX_LIMIT, via the
# max_limit= param below. Matches the fuzzy-fallback pool size already
# used for the same bounded-candidate-pool reasoning.
MAX_CANDIDATE_POOL = 500

# Typo-tolerance fallback, only triggered when the exact ilike search
# returns nothing. No pg_trgm/schema dependency -- this environment has no
# way to verify a Postgres extension migration would even be allowed on
# Railway's managed instance, so this stays pure Python/stdlib and behaves
# identically on SQLite (tests) and production Postgres.
#
# Bounded regardless of city size: fetches at most this many rank_score-
# ordered candidates to fuzzy-compare against, so a global (no city_id)
# fallback can't load the entire catalog into memory.
_FUZZY_CANDIDATE_POOL = 500
_FUZZY_MIN_SIMILARITY = 0.6

# Sentinel "distance" for a place with no coordinates, so it still sorts
# after every real match instead of needing dialect-specific NULLS LAST
# handling (SQLite/Postgres both handle a plain numeric ORDER BY the
# same way).
_NO_COORDS_DISTANCE_SQ = 1e18


def _clamp_limit(limit: int, max_limit: int = MAX_LIMIT) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(max_limit, n))


def _clamp_offset(offset: int) -> int:
    try:
        n = int(offset)
    except Exception:
        return 0
    return max(0, n)


def _fuzzy_fallback_search(
    db: Session,
    *,
    query: str,
    city_id: Optional[str],
    category_id: Optional[str],
    price_tier: Optional[int],
    limit: int,
) -> Tuple[List[Place], int]:
    """Typo-tolerant fallback for when the exact name match finds nothing.

    Fetches a bounded, rank_score-ordered candidate pool under the same
    non-name filters (city/category/price), then ranks candidates by
    difflib similarity to the query. Deliberately not merged into the
    exact-match query itself -- keeping the common case (a real substring
    match) a single cheap indexed ilike, and only paying the candidate-pool
    fetch + in-memory comparison cost on the genuinely-typo'd, zero-result
    case.
    """
    candidates_stmt = select(Place).where(Place.is_active.is_(True))

    if city_id:
        candidates_stmt = candidates_stmt.where(Place.city_id == city_id)

    if category_id:
        candidates_stmt = (
            candidates_stmt.join(
                place_categories,
                Place.id == place_categories.c.place_id,
            )
            .where(place_categories.c.category_id == category_id)
        )

    if price_tier is not None:
        candidates_stmt = candidates_stmt.where(Place.price_tier == price_tier)

    candidates_stmt = (
        candidates_stmt.distinct()
        .order_by(Place.rank_score.desc(), Place.id.asc())
        .limit(_FUZZY_CANDIDATE_POOL)
    )

    candidates = db.execute(candidates_stmt).scalars().all()

    query_lower = query.lower()
    scored: List[Tuple[float, Place]] = []
    for place in candidates:
        name = (place.name or "").lower()
        if not name:
            continue
        similarity = SequenceMatcher(None, query_lower, name).ratio()
        if similarity >= _FUZZY_MIN_SIMILARITY:
            scored.append((similarity, place))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    matched = [place for _, place in scored[:limit]]

    return matched, len(scored)


def _category_name_match(search_term: str):
    """Correlated EXISTS, not a join -- a place with several matching
    categories must still contribute exactly one row to the outer query,
    same as it would for a plain name match. Typing a cuisine/category
    name (e.g. "Italian", "sushi") previously matched nothing here unless
    a place's own *name* happened to contain that word -- the category
    taxonomy (Category.name, joined via place_categories) was never
    searched at all.
    """
    return exists(
        select(1)
        .select_from(place_categories)
        .join(Category, Category.id == place_categories.c.category_id)
        .where(
            place_categories.c.place_id == Place.id,
            Category.is_active.is_(True),
            Category.name.ilike(search_term),
        )
    )


def search_places(
    db: Session,
    *,
    query: str,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    max_limit: int = MAX_LIMIT,
) -> Tuple[List[Place], int]:

    limit = _clamp_limit(limit, max_limit)
    offset = _clamp_offset(offset)

    query = (query or "").strip()

    if not query:
        return [], 0

    search_term = f"%{query}%"

    stmt = select(Place).where(
        Place.is_active.is_(True),
        or_(Place.name.ilike(search_term), _category_name_match(search_term)),
    )

    if city_id:
        stmt = stmt.where(Place.city_id == city_id)

    if category_id:
        stmt = (
            stmt.join(
                place_categories,
                Place.id == place_categories.c.place_id,
            )
            .where(place_categories.c.category_id == category_id)
        )

    if price_tier is not None:
        stmt = stmt.where(Place.price_tier == price_tier)

    stmt = stmt.distinct()

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.execute(count_stmt).scalar_one()

    if total_count == 0:
        return _fuzzy_fallback_search(
            db,
            query=query,
            city_id=city_id,
            category_id=category_id,
            price_tier=price_tier,
            limit=limit,
        )

    # Without an explicit city scope, a name match is fetched from the
    # entire catalog ordered by rank_score alone — a real nearby match
    # with a modest rank_score can lose out to unrelated, higher-ranked
    # places in other cities and never even make it into this LIMIT
    # window, no matter how search_ranker.py re-sorts what *did* get
    # fetched. Ordering the fetch itself by proximity when the caller has
    # a location fixes that at the source: a true match near the caller
    # is now guaranteed a spot in the window regardless of how it
    # compares nationally, with rank_score only breaking ties among
    # similarly-distant results.
    if lat is not None and lng is not None:
        distance_sq = case(
            (Place.lat.is_(None), _NO_COORDS_DISTANCE_SQ),
            (Place.lng.is_(None), _NO_COORDS_DISTANCE_SQ),
            else_=(Place.lat - lat) * (Place.lat - lat) + (Place.lng - lng) * (Place.lng - lng),
        )
        # Postgres requires every SELECT DISTINCT query's ORDER BY
        # expressions to appear in the select list -- distance_sq is a
        # computed expression, not one of Place's own columns, so it has
        # to be added explicitly. add_columns() doesn't disturb .scalars()
        # below, which only extracts the first (Place) entity per row.
        # Confirmed live: this was a real, standing production bug --
        # SQLite (used by the local/default test suite) doesn't enforce
        # this rule, so it only ever surfaced against a real Postgres
        # instance (this repo's own CI runs the suite against Postgres
        # too, which is what caught it).
        stmt = stmt.add_columns(distance_sq.label("distance_sq"))
        order_by = (distance_sq.asc(), Place.rank_score.desc(), Place.id.asc())
    else:
        order_by = (Place.rank_score.desc(), Place.id.asc())

    stmt = stmt.order_by(*order_by).limit(limit).offset(offset)

    results = db.execute(stmt).scalars().all()

    return results, total_count