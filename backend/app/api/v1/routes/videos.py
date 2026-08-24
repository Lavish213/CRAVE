"""
app/api/v1/routes/videos.py

Short food-video upload + feed. Mirrors the request/confirm shape of
app/api/v1/endpoints/upload.py's photo flow (presigned R2 URL, then a
confirm call once the direct-to-storage PUT finishes) -- the actual
compress/food-score/approve pipeline runs out-of-process in the scheduler
worker (see app/services/video/video_processing_worker.py), not here.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.db.models.place_video import PlaceVideo, STATUS_APPROVED
from app.db.models.video_template import VideoTemplate
from app.services.upload.r2_client import generate_public_url
from app.services.video.video_upload_service import (
    request_video_upload_slot,
    confirm_video_upload,
    UploadForbiddenError,
)

router = APIRouter(prefix="/videos", tags=["videos"])


# -------------------------
# Request schemas
# -------------------------

class VideoRequestBody(BaseModel):
    place_id: str = Field(..., min_length=1, max_length=36)
    content_type: str = Field(..., min_length=1, max_length=64)
    template_id: Optional[str] = Field(None, max_length=64)
    # Client-generated id from the offline record flow (see
    # frontend/src/stores/videoQueueStore.ts) -- lets a retried request
    # after a crash/lost-response find the row it already created instead
    # of creating a duplicate. Omitted entirely for a video recorded with
    # a live connection, which never needs this.
    client_id: Optional[str] = Field(None, max_length=64)


# -------------------------
# POST /videos/request — issue a presigned upload URL
# -------------------------

@router.post("/request", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def request_upload(
    payload: VideoRequestBody = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = request_video_upload_slot(
            db,
            place_id=payload.place_id,
            content_type=payload.content_type,
            uploaded_by=user_id,
            template_id=payload.template_id,
            client_id=payload.client_id,
        )
        return result
    except UploadForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------
# POST /videos/{id}/confirm — client confirms the direct-to-storage PUT finished
# -------------------------

@router.post("/{video_id}/confirm", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def confirm_upload_endpoint(
    video_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        confirm_video_upload(db, video_id=video_id, user_id=user_id)
    except UploadForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        # Both "not found" (404-shaped) and "too large" (413-shaped)
        # currently raise ValueError from the service -- distinguish by
        # message rather than adding a second exception type for what's
        # still just "the request is invalid," matching this route's own
        # single-ValueError-branch convention elsewhere in this file.
        detail = str(e)
        status_code = 413 if "exceeds max upload size" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail)

    return {"ok": True}


# -------------------------
# GET /videos/feed — approved videos, newest first
#
# Registered BEFORE /{video_id} below on purpose: FastAPI matches routes
# in registration order, so if the dynamic /{video_id} path came first it
# would greedily match "feed" as a video_id, get no result, and return a
# confusing 404 from get_video_status instead of ever reaching this
# handler at all -- confirmed live by this file's own route test.
# -------------------------

@router.get("/feed", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_video_feed(
    place_id: Optional[str] = Query(None),
    limit: int = Query(15, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(PlaceVideo).filter(PlaceVideo.status == STATUS_APPROVED)
    if place_id:
        query = query.filter(PlaceVideo.place_id == place_id)

    rows = (
        query.order_by(PlaceVideo.created_at.desc(), PlaceVideo.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    videos = [
        {
            "id": v.id,
            "placeId": v.place_id,
            "templateId": v.template_id,
            "durationMs": v.duration_ms,
            "thumbnailUrl": generate_public_url(v.thumb_key) if v.thumb_key else None,
            "videoUrl": generate_public_url(v.processed_key) if v.processed_key else None,
        }
        for v in rows
    ]
    return {"videos": videos, "limit": limit, "offset": offset}


# -------------------------
# GET /videos/templates — active shot templates. Same route-ordering note
# as /feed above.
# -------------------------

@router.get("/templates", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def list_templates(db: Session = Depends(get_db)):
    templates = (
        db.query(VideoTemplate)
        .filter(VideoTemplate.active.is_(True))
        .order_by(VideoTemplate.sort_order.asc())
        .all()
    )
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "overlayAssetUrl": t.overlay_asset_url,
                "beatCues": t.beat_cues,
                "minFoodAreaPct": t.min_food_area_pct,
            }
            for t in templates
        ]
    }


# -------------------------
# GET /videos/{id} — poll status
# -------------------------

@router.get("/{video_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_video_status(
    video_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    video = db.query(PlaceVideo).filter(PlaceVideo.id == video_id).one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.uploaded_by != user_id:
        raise HTTPException(status_code=403, detail="Not your video")

    return {
        "id": video.id,
        "status": video.status,
        "rejectReason": video.reject_reason,
        "durationMs": video.duration_ms,
        "foodScore": video.food_score,
        "thumbnailUrl": generate_public_url(video.thumb_key) if video.thumb_key else None,
        "videoUrl": generate_public_url(video.processed_key) if video.processed_key else None,
    }
