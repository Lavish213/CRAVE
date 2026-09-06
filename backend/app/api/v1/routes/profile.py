# app/api/v1/routes/profile.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id, get_current_user_id_optional
from app.db.session import get_db
from app.services.profile import profile_service
from app.services.social.block_service import is_blocked
from app.services.social.taste_profile_service import get_taste_profile
from app.services.social.recommendation_service import get_match_score
from app.services.upload.r2_client import generate_presigned_upload_url, generate_public_url

router = APIRouter(prefix="/profile", tags=["profile"])

_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ProfileSetupRequest(BaseModel):
    username: str
    display_name: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    is_public: Optional[bool] = None


class AvatarUploadRequest(BaseModel):
    content_type: str


class ProfileOut(BaseModel):
    id: str
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    is_public: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/username-available", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def check_username_available(
    username: str = Query(..., min_length=1, max_length=30),
    db: Session = Depends(get_db),
):
    return {"available": profile_service.username_available(db, username)}


@router.post("/setup", response_model=ProfileOut, status_code=201, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def setup_profile(
    payload: ProfileSetupRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return profile_service.create_profile(
            db, user_id=user_id, username=payload.username, display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/me", response_model=ProfileOut, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_my_profile(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    profile = profile_service.get_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile not set up yet")
    return profile


@router.patch("/me", response_model=ProfileOut, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def update_my_profile(
    payload: ProfileUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return profile_service.update_profile(
            db, user_id=user_id, display_name=payload.display_name, bio=payload.bio,
            avatar_url=payload.avatar_url, is_public=payload.is_public,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/avatar/upload-url", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def request_avatar_upload_url(
    payload: AvatarUploadRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
):
    if payload.content_type not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="unsupported content type")

    import uuid
    ext = payload.content_type.split("/")[-1]
    key = f"avatars/{user_id}/{uuid.uuid4()}.{ext}"

    upload_url = generate_presigned_upload_url(key=key, content_type=payload.content_type)
    public_url = generate_public_url(key)

    # Client uploads directly to R2 with `upload_url`, then PATCHes
    # /profile/me with avatar_url=public_url once the PUT succeeds — no
    # background processing worker for a plain avatar image, unlike place
    # photos (no OCR/dedup/multi-size derivatives needed here).
    return {"upload_url": upload_url, "public_url": public_url}


@router.get("/{user_id}", response_model=ProfileOut, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_public_profile(
    user_id: str,
    db: Session = Depends(get_db),
    viewer_id: Optional[str] = Depends(get_current_user_id_optional),
):
    profile = profile_service.get_profile(db, user_id)
    # A private profile is still visible to its own owner -- previously this
    # only ever checked is_public, with no notion of who's asking, so a
    # signed-in user who had set their own profile private got "profile not
    # found" viewing their own /user/[id] page (reachable from their own
    # leaderboard row or a friend-ranking entry pointing at themselves).
    if not profile or (not profile.is_public and viewer_id != user_id):
        raise HTTPException(status_code=404, detail="profile not found")
    return profile


@router.get(
    "/{user_id}/taste",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def get_taste_profile_route(
    user_id: str,
    db: Session = Depends(get_db),
    viewer_id: Optional[str] = Depends(get_current_user_id_optional),
) -> dict:
    """
    "Taste Profile" — the equivalent of Beli's own stats screen (total
    places ranked, tier breakdown, favorite cuisine, top city,
    percentile). Gated on the same is_public check as GET /{user_id}
    (public profile) rather than a separate rule, so it's consistent
    with whatever visibility the person already chose for their profile
    -- except for the owner themselves, who can always see their own
    taste profile regardless of its visibility setting.

    Block enforcement now happens here too (previously client-side
    only, via GET /blocks/status -- a direct API call bypassed it
    entirely, since a blocked relationship never touched this route's
    own response). A blocked relationship is symmetric (see
    block_service.is_blocked): neither party can pull the other's
    activity-derived data, which taste stats are, through this route.

    Also includes "match_score" — Beli's pairwise taste-compatibility
    number — whenever the viewer is signed in and looking at someone
    else's profile. Auth is optional (get_current_user_id_optional)
    rather than required, since this route is otherwise viewable by a
    signed-out visitor; match_score is simply omitted (None) for them.
    """
    profile = profile_service.get_profile(db, user_id)
    if not profile or (not profile.is_public and viewer_id != user_id):
        raise HTTPException(status_code=404, detail="profile not found")
    if viewer_id and viewer_id != user_id and is_blocked(db, user_a=viewer_id, user_b=user_id):
        raise HTTPException(status_code=403, detail="blocked")
    taste = get_taste_profile(db, user_id=user_id)
    match_score = None
    if viewer_id and viewer_id != user_id:
        match_score = get_match_score(db, user_id=viewer_id, other_user_id=user_id)
    taste["match_score"] = match_score
    return taste
