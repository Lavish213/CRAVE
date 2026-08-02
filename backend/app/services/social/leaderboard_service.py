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
from app.services.social import follow_service


class LeaderboardError(ValueError):
    pass


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

    if among == "friends":
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

    # A leaderboard of opaque user ids is not a leaderboard. Resolve handles
    # in one query rather than one per row.
    profiles = {
        p.id: p
        for p in db.query(UserProfile)
        .filter(UserProfile.id.in_([r[0] for r in rows]))
        .all()
    }

    out = []
    for i, (uid, count) in enumerate(rows):
        profile = profiles.get(uid)
        out.append({
            "user_id": uid,
            "places_logged": count,
            "rank": i + 1,
            "username": profile.username if profile else None,
            "display_name": profile.display_name if profile else None,
            "avatar_url": profile.avatar_url if profile else None,
        })
    return out
