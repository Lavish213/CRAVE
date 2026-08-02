# app/api/v1/routes/rankings.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.services.personal_ranking import ranking_service
from app.services.personal_ranking.ranking_service import RankingError
from app.services.social.activity_service import record_ranked_place

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

    if result["status"] == "ranked":
        ranking = result["ranking"]
        record_ranked_place(
            db, user_id=ranking.user_id, place_id=ranking.place_id,
            tier=ranking.tier, score=ranking.rank_score,
        )
        db.commit()

    return _serialize_result(result)


@router.get("/me", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_my_rankings(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rankings = ranking_service.list_user_rankings(db, user_id)
    return {"rankings": [RankingOut.model_validate(r) for r in rankings]}


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
