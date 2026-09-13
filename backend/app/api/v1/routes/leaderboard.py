"""Compatibility boundary for the standalone social leaderboard outside V1."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def leaderboard(_user_id: str = Depends(get_current_user_id)):
    raise HTTPException(
        status_code=410,
        detail="The standalone social leaderboard is not part of CRAVE V1.",
    )
