# app/api/v1/routes/hitlist.py
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.hitlist.save_intake import intake_hitlist_save
from app.services.hitlist.suggest_intake import intake_suggestion
from app.services.hitlist.get_user_hitlist import get_user_hitlist
from app.services.hitlist.delete_save import delete_hitlist_save
from app.services.hitlist.analytics import get_hitlist_analytics
from app.api.v1.schemas.hitlist import (
    HitlistSaveRequest, HitlistSuggestRequest,
    HitlistResponse, HitlistItemOut, HitlistSuggestResponse,
)
from app.core.auth import require_api_key
from app.core.user_auth import get_current_user_id
from app.core.rate_limit import rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hitlist", tags=["hitlist"])


@router.post("/save", status_code=201, dependencies=[Depends(rate_limit)])
def save_to_hitlist(
    payload: HitlistSaveRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
):
    try:
        save = intake_hitlist_save(
            db=db,
            user_id=user_id,
            place_name=payload.place_name,
            source_url=payload.source_url,
            lat=payload.lat,
            lng=payload.lng,
        )
        db.commit()
        return {"status": "saved", "id": save.id, "dedup_key": save.dedup_key}
    except ValueError as exc:
        raise HTTPException(
            status_code=429 if "Rate limit" in str(exc) else 400,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.exception("hitlist_save_failed user=%s error=%s", user_id, exc)
        raise HTTPException(status_code=500, detail="Save failed")


@router.get("/analytics/summary", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def hitlist_analytics(db: Session = Depends(get_db)):
    return get_hitlist_analytics(db)


@router.delete("/delete", dependencies=[Depends(rate_limit)])
def delete_save(
    place_name: str = Query(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
):
    deleted = delete_hitlist_save(db=db, user_id=user_id, place_name=place_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Save not found")
    db.commit()
    return {"status": "deleted"}


@router.post("/suggest", response_model=HitlistSuggestResponse, status_code=201, dependencies=[Depends(rate_limit)])
def suggest_place(
    payload: HitlistSuggestRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
):
    try:
        suggestion = intake_suggestion(
            db=db,
            user_id=user_id,
            place_name=payload.place_name,
            source_url=payload.source_url,
            city_hint=payload.city_hint,
        )
        db.commit()
        return HitlistSuggestResponse.model_validate(suggestion)
    except ValueError as exc:
        raise HTTPException(
            status_code=429 if "Rate limit" in str(exc) else 400,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.exception("hitlist_suggest_failed user=%s error=%s", user_id, exc)
        raise HTTPException(status_code=500, detail="Suggestion failed")


@router.get("/me", response_model=HitlistResponse, dependencies=[Depends(rate_limit)])
def get_hitlist(
    include_resolved: bool = Query(True),
    include_unresolved: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
):
    """
    Was GET /{user_id} — a path param nobody verified, so anyone could pull
    anyone else's hitlist. Changed to /me: the id always comes from the
    verified token now. (Confirmed unused by the shipped frontend, which
    calls /saves instead — see CRAVE_REMEDIATION_PLAN.md section A.)
    """
    items = get_user_hitlist(
        db=db,
        user_id=user_id,
        include_resolved=include_resolved,
        include_unresolved=include_unresolved,
        limit=limit,
    )
    return HitlistResponse(
        items=[HitlistItemOut.model_validate(i) for i in items],
        total=len(items),
    )
