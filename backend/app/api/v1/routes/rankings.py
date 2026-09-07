# app/api/v1/routes/rankings.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.db.models.place import Place
from app.db.models.place_ranking import PlaceRanking
from app.db.models.user_profile import UserProfile
from app.services.personal_ranking import ranking_service
from app.services.personal_ranking.ranking_service import RankingError
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.recommendations.recommendation_event_service import record_rank_outcome
from app.services.social.activity_service import record_ranked_place
from app.services.social.block_service import is_blocked
from app.services.visit_evidence_service import latest_rank_eligible_by_place

router = APIRouter(prefix="/rankings", tags=["rankings"])


class StartRankingRequest(BaseModel):
    place_id: str
    tier: str
    visited_at: Optional[datetime] = None
    note: Optional[str] = None
    tags: Optional[List[str]] = None


class CompareRequest(BaseModel):
    comparison_token: str
    winner: str


class RankingOut(BaseModel):
    place_id: str
    tier: str
    rank_score: float
    note: Optional[str]
    tags: Optional[List[str]]
    visited_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RankedPlaceOut(RankingOut):
    """
    A ranking plus enough of its place to render a list row. Without the
    denormalized name/image here, a profile showing N ranked places would
    cost N extra round trips from mobile just to turn ids into something
    displayable — see get_primary_image_urls_bulk usage below.
    """

    name: Optional[str] = None
    primary_image_url: Optional[str] = None
    city_id: Optional[str] = None


class RankQueueItemOut(BaseModel):
    place_id: str
    name: str
    primary_image_url: Optional[str] = None
    city_id: Optional[str] = None
    visited_at: datetime
    evidence_tier: str
    evidence_source: str


class RankQueueResponse(BaseModel):
    items: List[RankQueueItemOut]


def _hydrate_rankings(db: Session, rankings: list) -> List[RankedPlaceOut]:
    """Attach place name/image/category in two bulk queries, not N+1."""
    if not rankings:
        return []

    place_ids = [r.place_id for r in rankings]
    places = {
        p.id: p for p in db.query(Place).filter(Place.id.in_(place_ids)).all()
    }
    image_urls = get_primary_image_urls_bulk(db, place_ids=list(places.keys()))

    out: List[RankedPlaceOut] = []
    for r in rankings:
        place = places.get(r.place_id)
        row = RankedPlaceOut.model_validate(r)
        if place:
            row = row.model_copy(update={
                "name": place.name,
                "primary_image_url": image_urls.get(place.id),
                "city_id": place.city_id,
            })
        out.append(row)
    return out


def _place_city_id(db: Session, place_id: str) -> Optional[str]:
    return db.query(Place.city_id).filter(Place.id == place_id).scalar()


def _serialize_result(result: dict) -> dict:
    if result["status"] == "ranked":
        return {"status": "ranked", "ranking": RankingOut.model_validate(result["ranking"])}
    return {
        "status": "comparing",
        "comparison_token": result["comparison_token"],
        "opponent_place_id": result["opponent_place_id"],
    }


@router.post("", status_code=201, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def start_ranking(
    payload: StartRankingRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = ranking_service.start_ranking(
            db, user_id=user_id, place_id=payload.place_id, tier=payload.tier,
            visited_at=payload.visited_at, note=payload.note, tags=payload.tags,
        )
    except RankingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if result["status"] == "ranked":
        record_ranked_place(
            db, user_id=user_id, place_id=payload.place_id,
            tier=payload.tier, score=result["ranking"].rank_score,
        )
        record_rank_outcome(
            db, user_id=user_id, place_id=payload.place_id,
            city_id=_place_city_id(db, payload.place_id),
        )
        db.commit()

    return _serialize_result(result)


@router.post("/compare", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def submit_comparison(
    payload: CompareRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = ranking_service.submit_comparison(
            db, token=payload.comparison_token, winner=payload.winner, expected_user_id=user_id,
        )
    except RankingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # already_existed=True means this call landed on a replay of an
    # already-fully-processed final comparison (see ranking_service's
    # IntegrityError handling) -- the activity event and any other
    # first-time-only side effects were already recorded when the
    # original request succeeded, and recording them again here would
    # duplicate them for no reason other than a network retry.
    if result["status"] == "ranked" and not result.get("already_existed"):
        ranking = result["ranking"]
        record_ranked_place(
            db, user_id=ranking.user_id, place_id=ranking.place_id,
            tier=ranking.tier, score=ranking.rank_score,
        )
        record_rank_outcome(
            db, user_id=ranking.user_id, place_id=ranking.place_id,
            city_id=_place_city_id(db, ranking.place_id),
        )
        db.commit()

    return _serialize_result(result)


@router.get("/queue", response_model=RankQueueResponse, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_rank_queue(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> RankQueueResponse:
    """
    Unranked places with declared/verified visit evidence, newest first.

    Inferred-only evidence is filtered in the shared visit-evidence service and
    can never appear here. Multiple visits remain stored factually but collapse
    to one queue row per place.
    """
    eligible = latest_rank_eligible_by_place(db, user_id=user_id, limit=max(limit * 2, limit))
    if not eligible:
        return RankQueueResponse(items=[])

    place_ids = [row.place_id for row in eligible]
    ranked_ids = {
        place_id
        for (place_id,) in db.query(PlaceRanking.place_id).filter(
            PlaceRanking.user_id == user_id,
            PlaceRanking.place_id.in_(place_ids),
        ).all()
    }
    unranked = [row for row in eligible if row.place_id not in ranked_ids][:limit]
    if not unranked:
        return RankQueueResponse(items=[])

    unranked_place_ids = [row.place_id for row in unranked]
    places = {
        place.id: place
        for place in db.query(Place).filter(
            Place.id.in_(unranked_place_ids),
            Place.is_active.is_(True),
        ).all()
    }
    image_urls = get_primary_image_urls_bulk(db, place_ids=list(places.keys()))

    items: List[RankQueueItemOut] = []
    for evidence in unranked:
        place = places.get(evidence.place_id)
        if not place:
            continue
        items.append(
            RankQueueItemOut(
                place_id=place.id,
                name=place.name,
                primary_image_url=image_urls.get(place.id),
                city_id=place.city_id,
                visited_at=evidence.occurred_at,
                evidence_tier=evidence.tier,
                evidence_source=evidence.source,
            )
        )
    return RankQueueResponse(items=items)


@router.get("/me", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_my_rankings(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return {"rankings": _hydrate_rankings(db, ranking_service.list_user_rankings(db, user_id))}


@router.get("/user/{target_user_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_user_rankings(
    target_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Someone else's ranked list — the thing a profile page is actually for.

    Previously this only ever checked is_public, discarding the caller's
    own identity entirely (the auth dependency existed but was never
    read) -- which meant an owner viewing their own private profile via
    this route got "profile not found" (see get_public_profile's
    identical historical bug), and separately meant a blocked caller
    could still pull the full ranked list directly against this route,
    with the block only ever enforced client-side by the app's own UI.
    Both are fixed the same way get_public_profile/taste were.
    """
    profile = (
        db.query(UserProfile).filter(UserProfile.id == target_user_id).one_or_none()
    )
    if not profile or (not profile.is_public and user_id != target_user_id):
        raise HTTPException(status_code=404, detail="profile not found")
    if user_id != target_user_id and is_blocked(db, user_a=user_id, user_b=target_user_id):
        raise HTTPException(status_code=403, detail="blocked")

    return {
        "rankings": _hydrate_rankings(db, ranking_service.list_user_rankings(db, target_user_id))
    }


@router.delete("/{place_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def delete_ranking(
    place_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    deleted = ranking_service.delete_ranking(db, user_id=user_id, place_id=place_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ranking not found")
    return {"status": "deleted"}