# app/api/v1/routes/account.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.db.models.device_push_token import VALID_PLATFORMS
from app.services.account.account_deletion_service import delete_account
from app.services.notifications.push_token_service import (
    register_push_token,
    unregister_push_token,
)

router = APIRouter(prefix="/account", tags=["account"])


class DeleteAccountRequest(BaseModel):
    # Cheap insurance against an accidental/retried DELETE actually
    # deleting something — the frontend must explicitly opt in, not just
    # hit the endpoint.
    confirm: bool = False


@router.delete("/me", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def delete_my_account(
    payload: DeleteAccountRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true")

    result = delete_account(db, user_id)
    return result


class RegisterPushTokenRequest(BaseModel):
    push_token: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(..., description="One of: " + ", ".join(sorted(VALID_PLATFORMS)))


@router.post("/push-token", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def register_push_token_endpoint(
    payload: RegisterPushTokenRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if payload.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail="platform must be ios or android")

    register_push_token(
        db, user_id=user_id, push_token=payload.push_token, platform=payload.platform
    )
    return {"ok": True}


@router.delete("/push-token/{push_token}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def unregister_push_token_endpoint(
    push_token: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    unregister_push_token(db, user_id=user_id, push_token=push_token)
    return {"ok": True}
