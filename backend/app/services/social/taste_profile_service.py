"""
Taste Profile — the direct equivalent of Beli's own "Taste Profile"
stats screen (confirmed via multiple independent sources: total
restaurants ranked, favorite cuisines, highest-ranked/most-visited
cities, and a percentile rank among other diners). Pure aggregation over
data CRAVE already has (PlaceRanking + categories) — no new table.

Deliberately excludes Beli's "Match Score" (pairwise taste compatibility
with a specific friend) — that needs a real user-similarity algorithm,
which is being built next for the personalized-recommendations feature
and will reuse it rather than duplicating the computation here.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.place_ranking import PlaceRanking
from app.db.models.place import Place
from app.db.models.city import City
from app.db.models.category import Category
from app.db.models.place_categories import place_categories

# Same generic-category exclusion as place_detail_router.py's own —
# "favorite cuisine: Restaurant" would be a meaningless result.
_GENERIC_CATEGORIES = {"restaurant", "restaurants", "bar", "bars", "other", "others"}

_TIER_KEYS = ("liked", "fine", "disliked")


def _compute_favorite_cuisine(db: Session, *, user_id: str) -> Optional[str]:
    # Prefer places the user actually liked — a cuisine that's merely
    # over-represented among places they ranked "fine" or "disliked"
    # isn't their favorite. Falls back to all ranked places only if
    # they've never logged a "liked" place yet.
    liked_place_ids = [
        row[0]
        for row in db.query(PlaceRanking.place_id)
        .filter(PlaceRanking.user_id == user_id, PlaceRanking.tier == "liked")
        .all()
    ]
    candidate_ids = liked_place_ids or [
        row[0]
        for row in db.query(PlaceRanking.place_id)
        .filter(PlaceRanking.user_id == user_id)
        .all()
    ]
    if not candidate_ids:
        return None

    rows = (
        db.query(Category.name, func.count(place_categories.c.place_id))
        .join(place_categories, place_categories.c.category_id == Category.id)
        .filter(place_categories.c.place_id.in_(candidate_ids))
        .group_by(Category.name)
        .order_by(func.count(place_categories.c.place_id).desc())
        .all()
    )
    for name, _count in rows:
        if (name or "").strip().lower() not in _GENERIC_CATEGORIES:
            return name
    return None


def _compute_top_city(db: Session, *, user_id: str) -> Optional[Dict[str, Any]]:
    row = (
        db.query(Place.city_id, func.count(PlaceRanking.id).label("cnt"))
        .join(PlaceRanking, PlaceRanking.place_id == Place.id)
        .filter(PlaceRanking.user_id == user_id)
        .group_by(Place.city_id)
        .order_by(func.count(PlaceRanking.id).desc())
        .first()
    )
    if not row:
        return None
    city_id, count = row
    city = db.query(City).filter(City.id == city_id).one_or_none()
    if not city:
        return None
    return {"id": city.id, "name": city.name, "count": int(count)}


def _compute_percentile(db: Session, *, user_id: str, total_ranked: int) -> Optional[int]:
    """
    "You've ranked more places than X% of people" — global across all
    users (not city-scoped), by explicit choice: with a small and
    growing user base, a per-city percentile would be either meaningless
    (denominator of 1-2 people) or misleadingly volatile; this can be
    revisited once there's enough data per city for it to mean anything.
    """
    if total_ranked == 0:
        return None

    counts_by_user = dict(
        db.query(PlaceRanking.user_id, func.count(PlaceRanking.id))
        .group_by(PlaceRanking.user_id)
        .all()
    )
    others = [c for uid, c in counts_by_user.items() if uid != user_id]
    if not others:
        return 100

    fewer_or_equal = sum(1 for c in others if c <= total_ranked)
    return round((fewer_or_equal / len(others)) * 100)


def get_taste_profile(db: Session, *, user_id: str) -> Dict[str, Any]:
    rankings = db.query(PlaceRanking).filter(PlaceRanking.user_id == user_id).all()
    total_ranked = len(rankings)

    tier_counts = {key: 0 for key in _TIER_KEYS}
    for r in rankings:
        if r.tier in tier_counts:
            tier_counts[r.tier] += 1

    return {
        "total_ranked": total_ranked,
        "tier_counts": tier_counts,
        "favorite_cuisine": _compute_favorite_cuisine(db, user_id=user_id),
        "top_city": _compute_top_city(db, user_id=user_id),
        "percentile": _compute_percentile(db, user_id=user_id, total_ranked=total_ranked),
    }
