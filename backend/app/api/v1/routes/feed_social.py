"""Compatibility boundary for the retired standalone friends feed."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/friends", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_friends_feed(_user_id: str = Depends(get_current_user_id)):
    raise HTTPException(
        status_code=410,
        detail="The standalone friends feed has moved to the main Feed.",
    )
