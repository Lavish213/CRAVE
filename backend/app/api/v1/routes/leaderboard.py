# app/api/v1/routes/leaderboard.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.services.social.leaderboard_service import LeaderboardError, get_leaderboard

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def leaderboard(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    among: str = Query("global", pattern="^(global|friends)$"),
    city_slug: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    try:
        rows = get_leaderboard(
            db, user_id=user_id, among=among, city_slug=city_slug, limit=limit
        )
    except LeaderboardError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"leaderboard": rows}
