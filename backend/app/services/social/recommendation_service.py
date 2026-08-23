"""
Personalized recommendations — Beli's "prediction score" feed, confirmed
via research as standard user-based collaborative filtering: at CRAVE's
current scale (small user base, no ML infra deployed) a lightweight
cosine-similarity model over shared PlaceRanking rows is the right level
of sophistication, not a new recommender-system dependency.

Also powers "Match Score" (Beli's pairwise taste-compatibility number
shown on a friend's profile) — deliberately reuses this exact similarity
computation rather than a second bespoke one (see
taste_profile_service.py's module docstring, which explicitly deferred
Match Score to this file for that reason).

Algorithm, for a target user U:
1. Build U's rank_score vector: {place_id: rank_score} over everything
   they've ranked.
2. Find every OTHER user who ranked at least MIN_SHARED_PLACES of those
   same places (excluding anyone blocked in either direction), and
   compute cosine similarity between the two vectors restricted to the
   shared place_ids.
3. Keep the positively-correlated users, weight every place THEY ranked
   (that U hasn't already ranked or saved) by similarity * their
   rank_score, and sum across similar users.
4. Return the highest-scoring places.

Cold start (no ranking history yet, or no similar users found) falls
back to the highest-rank_score active places U hasn't already ranked or
saved — never personalized, but never an empty screen either.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_ranking import PlaceRanking
from app.db.models.hitlist_save import HitlistSave
from app.services.social import block_service

# Below this many co-ranked places, a similarity score is noise, not
# signal -- two users who happen to have both ranked exactly one shared
# place agree "perfectly" by construction, which says nothing real about
# their taste overlap.
MIN_SHARED_PLACES = 2

MAX_SIMILAR_USERS = 50
DEFAULT_LIMIT = 20


def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> Optional[float]:
    shared = set(a) & set(b)
    if len(shared) < MIN_SHARED_PLACES:
        return None
    dot = sum(a[pid] * b[pid] for pid in shared)
    norm_a = math.sqrt(sum(a[pid] ** 2 for pid in shared))
    norm_b = math.sqrt(sum(b[pid] ** 2 for pid in shared))
    if norm_a == 0 or norm_b == 0:
        return None
    return dot / (norm_a * norm_b)


def _user_ranking_vector(db: Session, *, user_id: str) -> Dict[str, float]:
    rows = (
        db.query(PlaceRanking.place_id, PlaceRanking.rank_score)
        .filter(PlaceRanking.user_id == user_id)
        .all()
    )
    return {place_id: score for place_id, score in rows}


def _find_similar_users(
    db: Session,
    *,
    user_id: str,
    my_vector: Dict[str, float],
    excluded_user_ids: Set[str],
) -> List[Tuple[str, float]]:
    if not my_vector:
        return []

    rows = (
        db.query(PlaceRanking.user_id, PlaceRanking.place_id, PlaceRanking.rank_score)
        .filter(
            PlaceRanking.place_id.in_(list(my_vector.keys())),
            PlaceRanking.user_id != user_id,
        )
        .all()
    )

    vectors_by_user: Dict[str, Dict[str, float]] = {}
    for uid, place_id, score in rows:
        if uid in excluded_user_ids:
            continue
        vectors_by_user.setdefault(uid, {})[place_id] = score

    similarities: List[Tuple[str, float]] = []
    for uid, vector in vectors_by_user.items():
        sim = _cosine_similarity(my_vector, vector)
        if sim is not None and sim > 0:
            similarities.append((uid, sim))

    similarities.sort(key=lambda pair: pair[1], reverse=True)
    return similarities[:MAX_SIMILAR_USERS]


def _cold_start_places(
    db: Session,
    *,
    exclude_place_ids: Set[str],
    limit: int,
) -> List[Place]:
    query = db.query(Place).filter(Place.is_active.is_(True))
    if exclude_place_ids:
        query = query.filter(Place.id.notin_(exclude_place_ids))
    return (
        query.order_by(Place.rank_score.desc(), Place.id.asc())
        .limit(limit)
        .all()
    )


def get_recommendations(
    db: Session,
    *,
    user_id: str,
    limit: int = DEFAULT_LIMIT,
) -> List[Place]:
    my_vector = _user_ranking_vector(db, user_id=user_id)

    saved_place_ids = {
        row[0]
        for row in db.query(HitlistSave.place_id)
        .filter(HitlistSave.user_id == user_id, HitlistSave.place_id.isnot(None))
        .all()
    }
    exclude_ids: Set[str] = set(my_vector.keys()) | saved_place_ids

    excluded_users = set(block_service.blocked_user_ids_either_direction(db, user_id))
    similar_users = _find_similar_users(
        db, user_id=user_id, my_vector=my_vector, excluded_user_ids=excluded_users
    )

    if not similar_users:
        return _cold_start_places(db, exclude_place_ids=exclude_ids, limit=limit)

    similarity_by_user = dict(similar_users)
    candidate_rows = (
        db.query(PlaceRanking.place_id, PlaceRanking.user_id, PlaceRanking.rank_score)
        .filter(PlaceRanking.user_id.in_(list(similarity_by_user.keys())))
        .all()
    )

    place_scores: Dict[str, float] = {}
    for place_id, uid, score in candidate_rows:
        if place_id in exclude_ids:
            continue
        weight = similarity_by_user.get(uid, 0.0)
        place_scores[place_id] = place_scores.get(place_id, 0.0) + weight * score

    ranked_ids = sorted(place_scores, key=lambda pid: place_scores[pid], reverse=True)[:limit]

    places = (
        db.query(Place)
        .filter(Place.id.in_(ranked_ids), Place.is_active.is_(True))
        .all()
        if ranked_ids
        else []
    )
    places_by_id = {p.id: p for p in places}
    # Preserve score order -- the IN() query above has no ORDER BY tied to it.
    ordered = [places_by_id[pid] for pid in ranked_ids if pid in places_by_id]

    if len(ordered) < limit:
        backfill_exclude = exclude_ids | set(ranked_ids)
        backfill = _cold_start_places(
            db, exclude_place_ids=backfill_exclude, limit=limit - len(ordered)
        )
        ordered.extend(backfill)

    return ordered


def get_match_score(db: Session, *, user_id: str, other_user_id: str) -> Optional[int]:
    """
    "Match Score" -- percentage taste-compatibility between two users,
    derived from the same cosine similarity used for recommendations.
    None if they don't share enough ranked places yet for the number to
    mean anything (see MIN_SHARED_PLACES) -- callers should treat None as
    "not enough data," not zero compatibility.
    """
    if user_id == other_user_id:
        return None

    my_vector = _user_ranking_vector(db, user_id=user_id)
    their_vector = _user_ranking_vector(db, user_id=other_user_id)
    sim = _cosine_similarity(my_vector, their_vector)
    if sim is None:
        return None

    # rank_score is always >= 0 (see TIER_SCORE_BANDS), so cosine
    # similarity here is already bounded to [0, 1] in practice -- this is
    # a direct percentage, not a rescale from the general [-1, 1] range.
    return round(max(0.0, min(1.0, sim)) * 100)
