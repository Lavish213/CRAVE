# app/services/personal_ranking/ranking_service.py
"""
The comparison-based ranking engine — reverse-engineered from how Beli's
own flow actually works (see session research): pick a coarse tier, then
answer a handful of "which was better" pairwise comparisons that binary-
insert the new place into your existing ranked list for that tier. The
final score is interpolated from where it lands, not assigned directly.

Two deviations from Beli's literal mechanic, both driven by its own most
common user complaint (documented across app-store reviews and design
critiques): forcing a comparison between two places that aren't actually
alike — a bagel shop against a steakhouse — reads as unfair and makes the
resulting score feel wrong, and users specifically ask to opt out of a
comparison they don't have a real opinion on.

  1. Comparisons are scoped to places sharing a cuisine-type category.
     A new ranking only ever competes against same-cuisine places already
     in that tier; if this is the first place of that cuisine in the
     tier, it's placed at the tier's band midpoint with zero comparisons,
     the same as being the first entry in the tier at all. This means
     rank_score is a same-cuisine ordering mapped onto the tier's band,
     not a strict cross-cuisine total order — a deliberate trade: Beli's
     unified list is the thing users say feels unfair.
  2. "skip" is a third valid comparison outcome (alongside "new" and
     "opponent"), for "I can't call this one." It converges the search at
     the current midpoint instead of continuing to narrow — landing the
     new place right next to the opponent rather than forcing a verdict.

Session state between comparison rounds is a signed, short-lived JWT (not
a DB row) carrying the binary-search bounds — nothing to clean up, and it
can't be tampered with client-side since it's HMAC-signed with the app's
own secret_key.

Concurrency note: bounds are list *indices*, re-resolved against a fresh
query each round. If the same user's tier list changed from another
device mid-comparison (rare — one person doesn't run two ranking flows on
the same tier in parallel) the final placement could be slightly off;
not worth a locking scheme for that edge case.
"""
from __future__ import annotations

import time
from typing import Optional

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models.category import Category, CategoryType
from app.db.models.place import Place
from app.db.models.place_ranking import (
    TIER_SCORE_BANDS,
    VALID_TIERS,
    PlaceRanking,
)

_TOKEN_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 15 * 60
_VALID_WINNERS = ("new", "opponent", "skip")


class RankingError(ValueError):
    pass


def _cuisine_category_ids(place: Place) -> list[str]:
    return sorted({c.id for c in place.categories if c.type == CategoryType.cuisine})


def _tier_list(
    db: Session, *, user_id: str, tier: str, category_ids: Optional[list[str]] = None
) -> list[PlaceRanking]:
    query = db.query(PlaceRanking).filter(
        PlaceRanking.user_id == user_id, PlaceRanking.tier == tier
    )
    if category_ids:
        query = query.join(Place, PlaceRanking.place_id == Place.id).filter(
            Place.categories.any(Category.id.in_(category_ids))
        )
    return query.order_by(PlaceRanking.rank_score.asc()).all()


def _sign_state(payload: dict) -> str:
    to_sign = dict(payload)
    to_sign["exp"] = int(time.time()) + _TOKEN_TTL_SECONDS
    return jwt.encode(to_sign, settings.secret_key, algorithm=_TOKEN_ALGORITHM)


def _verify_state(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_TOKEN_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise RankingError(f"invalid or expired comparison token: {exc}") from exc


def _finalize_score(tier: str, tier_list: list[PlaceRanking], insertion_index: int) -> float:
    band_lo, band_hi = TIER_SCORE_BANDS[tier]

    lower_neighbor = tier_list[insertion_index - 1] if insertion_index > 0 else None
    upper_neighbor = tier_list[insertion_index] if insertion_index < len(tier_list) else None

    low_bound = lower_neighbor.rank_score if lower_neighbor else band_lo
    high_bound = upper_neighbor.rank_score if upper_neighbor else band_hi

    return (low_bound + high_bound) / 2.0


def _create_ranking(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    tier: str,
    score: float,
    visited_at,
    note: Optional[str],
    tags: Optional[list],
) -> PlaceRanking:
    ranking = PlaceRanking(
        user_id=user_id,
        place_id=place_id,
        tier=tier,
        rank_score=score,
        visited_at=visited_at,
        note=note,
        tags=tags,
    )
    db.add(ranking)
    db.flush()
    return ranking


def start_ranking(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    tier: str,
    visited_at=None,
    note: Optional[str] = None,
    tags: Optional[list] = None,
) -> dict:
    if tier not in VALID_TIERS:
        raise RankingError(f"tier must be one of {sorted(VALID_TIERS)}")

    place = db.query(Place).filter(Place.id == place_id).one_or_none()
    if not place:
        raise RankingError("place not found")

    if db.query(PlaceRanking.id).filter(
        PlaceRanking.user_id == user_id, PlaceRanking.place_id == place_id
    ).first():
        raise RankingError(
            "place already ranked — DELETE the existing ranking first to re-rank it"
        )

    category_ids = _cuisine_category_ids(place)
    tier_list = _tier_list(db, user_id=user_id, tier=tier, category_ids=category_ids)

    if not tier_list:
        # First entry in this tier (or first of this cuisine within the
        # tier) — nothing comparable to compare against yet.
        score = (TIER_SCORE_BANDS[tier][0] + TIER_SCORE_BANDS[tier][1]) / 2.0
        ranking = _create_ranking(
            db, user_id=user_id, place_id=place_id, tier=tier, score=score,
            visited_at=visited_at, note=note, tags=tags,
        )
        db.commit()
        return {"status": "ranked", "ranking": ranking}

    lo, hi = 0, len(tier_list)
    mid = (lo + hi) // 2
    opponent = tier_list[mid]

    token = _sign_state({
        "user_id": user_id, "place_id": place_id, "tier": tier,
        "category_ids": category_ids,
        "lo": lo, "hi": hi,
        "visited_at": visited_at.isoformat() if visited_at else None,
        "note": note, "tags": tags,
    })
    return {"status": "comparing", "comparison_token": token, "opponent_place_id": opponent.place_id}


def submit_comparison(
    db: Session, *, token: str, winner: str, expected_user_id: Optional[str] = None
) -> dict:
    if winner not in _VALID_WINNERS:
        raise RankingError(f"winner must be one of {_VALID_WINNERS}")

    state = _verify_state(token)
    user_id = state["user_id"]
    place_id = state["place_id"]

    if expected_user_id is not None and user_id != expected_user_id:
        raise RankingError("this comparison token belongs to a different user")
    tier = state["tier"]
    category_ids = state.get("category_ids") or []
    lo, hi = state["lo"], state["hi"]

    tier_list = _tier_list(db, user_id=user_id, tier=tier, category_ids=category_ids)
    # Defensive clamp — see concurrency note in the module docstring.
    hi = min(hi, len(tier_list))
    lo = min(lo, hi)

    mid = (lo + hi) // 2

    if winner == "new":
        lo = mid + 1
    elif winner == "opponent":
        hi = mid
    else:
        # "skip" ("I can't call this one") converges right here instead of
        # narrowing further — the new place lands next to this opponent
        # rather than the flow forcing a verdict neither side earned.
        lo = hi = mid

    if lo < hi:
        next_mid = (lo + hi) // 2
        opponent = tier_list[next_mid]
        next_token = _sign_state({
            "user_id": user_id, "place_id": place_id, "tier": tier,
            "category_ids": category_ids,
            "lo": lo, "hi": hi,
            "visited_at": state.get("visited_at"), "note": state.get("note"),
            "tags": state.get("tags"),
        })
        return {
            "status": "comparing",
            "comparison_token": next_token,
            "opponent_place_id": opponent.place_id,
        }

    # Converged — lo == hi is the final insertion index.
    from datetime import datetime

    visited_at = datetime.fromisoformat(state["visited_at"]) if state.get("visited_at") else None
    score = _finalize_score(tier, tier_list, lo)

    # The comparison token is a stateless, replayable JWT by design (see
    # module docstring) — nothing marks it "already consumed" once the
    # final round's winner is submitted. If that response is lost to a
    # network blip after the server-side commit already succeeded, the
    # client's only option is to resubmit the identical final token+winner,
    # which would otherwise hit PlaceRanking's uq_place_rankings_user_place
    # unique constraint as an uncaught IntegrityError -> bare 500, for an
    # action that had, in fact, already fully succeeded. Treat that
    # specific race as success: return the ranking that already exists
    # rather than trying to create a second one.
    try:
        ranking = _create_ranking(
            db, user_id=user_id, place_id=place_id, tier=tier, score=score,
            visited_at=visited_at, note=state.get("note"), tags=state.get("tags"),
        )
        db.commit()
        return {"status": "ranked", "ranking": ranking, "already_existed": False}
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(PlaceRanking)
            .filter(PlaceRanking.user_id == user_id, PlaceRanking.place_id == place_id)
            .one_or_none()
        )
        if existing is None:
            # Constraint violation for some other reason than the replay
            # this is meant to tolerate -- don't swallow it.
            raise
        return {"status": "ranked", "ranking": existing, "already_existed": True}


def list_user_rankings(db: Session, user_id: str) -> list[PlaceRanking]:
    return (
        db.query(PlaceRanking)
        .filter(PlaceRanking.user_id == user_id)
        .order_by(PlaceRanking.rank_score.desc())
        .all()
    )


def delete_ranking(db: Session, *, user_id: str, place_id: str) -> bool:
    ranking = (
        db.query(PlaceRanking)
        .filter(PlaceRanking.user_id == user_id, PlaceRanking.place_id == place_id)
        .one_or_none()
    )
    if not ranking:
        return False
    db.delete(ranking)
    db.commit()
    return True


def update_ranking_metadata(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    note: Optional[str] = None,
    tags: Optional[list] = None,
    visited_at=None,
) -> PlaceRanking:
    ranking = (
        db.query(PlaceRanking)
        .filter(PlaceRanking.user_id == user_id, PlaceRanking.place_id == place_id)
        .one_or_none()
    )
    if not ranking:
        raise RankingError("ranking not found")

    if note is not None:
        ranking.note = note
    if tags is not None:
        ranking.tags = tags
    if visited_at is not None:
        ranking.visited_at = visited_at

    db.commit()
    return ranking
