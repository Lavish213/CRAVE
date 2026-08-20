# app/api/v1/routes/blocks.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.services.social import block_service

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.post("/{target_user_id}", status_code=201, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def block(
    target_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        block_service.block_user(db, blocker_id=user_id, blocked_id=target_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "blocked"}


@router.delete("/{target_user_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def unblock(
    target_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    block_service.unblock_user(db, blocker_id=user_id, blocked_id=target_user_id)
    return {"status": "not_blocked"}


@router.get("/status/{target_user_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def block_status(
    target_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return {"blocked": block_service.is_blocked(db, user_a=user_id, user_b=target_user_id)}


@router.get("", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_blocked(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return {"user_ids": block_service.list_blocked(db, user_id, limit=limit, offset=offset)}
