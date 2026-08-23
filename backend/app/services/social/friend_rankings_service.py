"""
"Which of my friends have ranked this place" — the direct equivalent of
Beli's "friend rating" feature (an averaged/aggregated view of your
friends' scores for a specific restaurant), which CRAVE had the
underlying data for (PlaceRanking + the follow graph) but never surfaced
anywhere on the place detail screen.
"""
from __future__ import annotations

from typing import List, TypedDict

from sqlalchemy.orm import Session

from app.db.models.place_ranking import PlaceRanking
from app.db.models.user_profile import UserProfile
from app.services.social import follow_service


class FriendRanking(TypedDict):
    user_id: str
    username: str
    display_name: str | None
    avatar_url: str | None
    tier: str
    rank_score: float


def get_friend_rankings_for_place(
    db: Session,
    *,
    place_id: str,
    user_id: str,
    limit: int = 20,
) -> List[FriendRanking]:
    """
    Rankings of `place_id` by people `user_id` follows, best-to-worst.

    Block-safe for free: a blocked user can never appear in
    list_following's result (block_user clears the follow relationship
    in both directions — see block_service.block_user), same reasoning
    already relied on by leaderboard_service's "among=friends" branch.
    """
    followee_ids = follow_service.list_following(db, user_id, limit=500, offset=0)
    if not followee_ids:
        return []

    rows = (
        db.query(PlaceRanking, UserProfile)
        .join(UserProfile, UserProfile.id == PlaceRanking.user_id)
        .filter(
            PlaceRanking.place_id == place_id,
            PlaceRanking.user_id.in_(followee_ids),
        )
        .order_by(PlaceRanking.rank_score.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "user_id": ranking.user_id,
            "username": profile.username,
            "display_name": profile.display_name,
            "avatar_url": profile.avatar_url,
            "tier": ranking.tier,
            "rank_score": float(ranking.rank_score),
        }
        for ranking, profile in rows
    ]
