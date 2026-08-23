# app/services/social/leaderboard_service.py
"""
Ranks users by how many places they've logged — Beli's actual leaderboard
metric (activity/exploration breadth), not average taste score. Pure
read-query on place_rankings; no new table.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_ranking import PlaceRanking
from app.db.models.user_profile import UserProfile
from app.services.social import block_service, follow_service
from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import leaderboard_global_base_key
from app.services.cache.cache_ttl import LEADERBOARD_TTL


class LeaderboardError(ValueError):
    pass


# How many top-ranked users to fetch (and cache) for the *global* board,
# regardless of what `limit` any individual request asks for. Deliberately
# not keyed to `limit` -- caching per-limit would fragment the cache into
# one entry per distinct limit value callers happen to request, when the
# underlying ranked list is the same list either way. Generous enough that
# a viewer with a handful of blocks still gets a full page after
# per-viewer filtering; a global board this deep essentially never
# actually needs more than this in practice.
_GLOBAL_POOL_SIZE = 200


def _fetch_global_base_ranking(
    db: Session,
    *,
    city_slug: Optional[str],
) -> list[dict]:
    """
    The *shared* global ranking -- identical for every viewer, which is
    exactly what makes it cacheable. Deliberately has no block-filtering
    baked in: that's applied per-viewer, after this is read from cache
    (see get_leaderboard) -- the same reason /place/{id}/friends is never
    folded into the shared place-detail cache. Also has no `rank` field
    yet: rank means "your position among what you can see," which can
    only be computed after the viewer's own block-filter is applied.
    """
    cache_key = leaderboard_global_base_key(city_slug=city_slug)
    cached = response_cache.get(cache_key)
    if cached is not None:
        return cached

    query = db.query(
        PlaceRanking.user_id, func.count(PlaceRanking.id).label("places_logged")
    )

    if city_slug:
        city = db.query(City).filter(City.slug == city_slug).one_or_none()
        if not city:
            raise LeaderboardError(f"city not found: {city_slug!r}")
        query = query.join(Place, Place.id == PlaceRanking.place_id).filter(
            Place.city_id == city.id
        )

    rows = (
        query.group_by(PlaceRanking.user_id)
        .order_by(func.count(PlaceRanking.id).desc())
        .limit(_GLOBAL_POOL_SIZE)
        .all()
    )

    if not rows:
        response_cache.set(cache_key, [], LEADERBOARD_TTL)
        return []

    profiles = {
        p.id: p
        for p in db.query(UserProfile)
        .filter(UserProfile.id.in_([r[0] for r in rows]))
        .all()
    }

    base = [
        {
            "user_id": uid,
            "places_logged": count,
            "username": profiles[uid].username if uid in profiles else None,
            "display_name": profiles[uid].display_name if uid in profiles else None,
            "avatar_url": profiles[uid].avatar_url if uid in profiles else None,
        }
        for uid, count in rows
    ]
    response_cache.set(cache_key, base, LEADERBOARD_TTL)
    return base


def get_leaderboard(
    db: Session,
    *,
    user_id: str,
    among: str = "global",
    city_slug: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    if among not in ("global", "friends"):
        raise LeaderboardError("among must be 'global' or 'friends'")

    if among == "friends":
        # Already block-safe: blocking clears the follow relationship in
        # both directions (see block_service.block_user), so a blocked
        # user can never appear in list_following's result. Inherently
        # per-viewer (scoped to who *you* follow) -- not cacheable the
        # way the global board is.
        query = db.query(
            PlaceRanking.user_id, func.count(PlaceRanking.id).label("places_logged")
        )
        if city_slug:
            city = db.query(City).filter(City.slug == city_slug).one_or_none()
            if not city:
                raise LeaderboardError(f"city not found: {city_slug!r}")
            query = query.join(Place, Place.id == PlaceRanking.place_id).filter(
                Place.city_id == city.id
            )
        followee_ids = follow_service.list_following(db, user_id, limit=500, offset=0)
        scoped_ids = followee_ids + [user_id]
        query = query.filter(PlaceRanking.user_id.in_(scoped_ids))

        rows = (
            query.group_by(PlaceRanking.user_id)
            .order_by(func.count(PlaceRanking.id).desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return []
        profiles = {
            p.id: p
            for p in db.query(UserProfile)
            .filter(UserProfile.id.in_([r[0] for r in rows]))
            .all()
        }
        return [
            {
                "user_id": uid,
                "places_logged": count,
                "rank": i + 1,
                "username": profiles[uid].username if uid in profiles else None,
                "display_name": profiles[uid].display_name if uid in profiles else None,
                "avatar_url": profiles[uid].avatar_url if uid in profiles else None,
            }
            for i, (uid, count) in enumerate(rows)
        ]

    # "global" -- shared cache, block-filtered per viewer after the read.
    base = _fetch_global_base_ranking(db, city_slug=city_slug)
    excluded_ids = block_service.blocked_user_ids_either_direction(db, user_id)
    visible = (
        [row for row in base if row["user_id"] not in excluded_ids]
        if excluded_ids
        else base
    )
    return [
        {**row, "rank": i + 1}
        for i, row in enumerate(visible[:limit])
    ]
