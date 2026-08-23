# FILE: backend/app/api/v1/routes/streak.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.services.social.streak_service import get_streak, record_activity

router = APIRouter(prefix="/streak", tags=["streak"])


class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    last_active_date: Optional[str] = None


class StreakPingRequest(BaseModel):
    # IANA timezone name, e.g. "America/Los_Angeles" -- used only to
    # compute the correct calendar day for the streak boundary. See
    # streak_service's module docstring for why the instant itself still
    # only ever comes from the server, never this value.
    timezone: Optional[str] = None


def _to_out(state) -> StreakOut:
    return StreakOut(
        current_streak=state.current_streak,
        longest_streak=state.longest_streak,
        last_active_date=state.last_active_date.isoformat() if state.last_active_date else None,
    )


@router.get(
    "/me",
    response_model=StreakOut,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def get_my_streak(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> StreakOut:
    """Read-only -- does not record activity. Call POST /streak/ping for that."""
    return _to_out(get_streak(db, user_id=user_id))


@router.post(
    "/ping",
    response_model=StreakOut,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def ping_streak(
    body: StreakPingRequest = Body(default=StreakPingRequest()),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> StreakOut:
    """
    Called by the app on open/foreground. Idempotent for the same
    calendar day -- safe to call more than once per day.
    """
    return _to_out(record_activity(db, user_id=user_id, client_timezone=body.timezone))
