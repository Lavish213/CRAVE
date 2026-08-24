# app/api/v1/routes/moderation.py
"""
Reactive moderation: user reports, plus the queue a human resolves them
from.

Automation catches what it can measure — unsafe, blurry, duplicate. It
cannot catch a sharp, well-lit, entirely safe photo that is simply of the
wrong restaurant, or someone's face, or last year's menu. That's what
reports are for, and until this existed there was no takedown path at all
short of direct database access.

The review endpoints are gated on an ADMIN_USER_IDS allowlist. That is
deliberately the crudest possible mechanism: there is no role system in
this app, and inventing one here would be a bigger change than the feature
warrants. It fails closed — an unset allowlist means nobody can review.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.db.models.image_report import (
    AUTO_HIDE_REPORT_COUNT,
    VALID_REPORT_REASONS,
    ImageReport,
)
from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_HIDDEN,
)
from app.services.images.place_image_invariant_service import PlaceImageInvariantService
from app.services.upload.r2_client import generate_public_url
from app.services.images.upload_moderation import (
    MOD_APPROVED,
    MOD_PENDING_REVIEW,
    MOD_REJECTED,
)
from app.db.models.video_report import (
    AUTO_HIDE_REPORT_COUNT as VIDEO_AUTO_HIDE_REPORT_COUNT,
    VALID_REPORT_REASONS as VALID_VIDEO_REPORT_REASONS,
    VideoReport,
)
from app.db.models.place_video import (
    PlaceVideo,
    MOD_APPROVED as VIDEO_MOD_APPROVED,
    MOD_PENDING_REVIEW as VIDEO_MOD_PENDING_REVIEW,
    MOD_REJECTED as VIDEO_MOD_REJECTED,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/moderation", tags=["moderation"])


def _admin_ids() -> set[str]:
    raw = os.getenv("ADMIN_USER_IDS", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def require_admin(user_id: str = Depends(get_current_user_id)) -> str:
    if user_id not in _admin_ids():
        # 404 rather than 403 — don't advertise that the queue exists.
        raise HTTPException(status_code=404, detail="Not found")
    return user_id


class ReportRequest(BaseModel):
    reason: str = Field(..., description="One of: " + ", ".join(sorted(VALID_REPORT_REASONS)))
    note: Optional[str] = Field(None, max_length=500)


class ReviewRequest(BaseModel):
    decision: str = Field(..., description="approve | reject")


@router.post(
    "/images/{image_id}/report",
    status_code=201,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def report_image(
    image_id: str,
    payload: ReportRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if payload.reason not in VALID_REPORT_REASONS:
        raise HTTPException(status_code=400, detail="invalid reason")

    image = db.query(PlaceImage).filter(PlaceImage.id == image_id).one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="image not found")

    report = ImageReport(
        image_id=image_id,
        reporter_id=user_id,
        reason=payload.reason,
        note=(payload.note or "").strip() or None,
    )
    db.add(report)
    try:
        db.flush()
    except IntegrityError:
        # Already reported by this user — idempotent, not an error worth
        # showing them.
        db.rollback()
        return {"status": "already_reported"}

    distinct_reports = (
        db.query(ImageReport.id).filter(ImageReport.image_id == image_id).count()
    )

    # Enough independent people flagged it that leaving it live is the
    # riskier bet. Held for review, never deleted — a coordinated bad-faith
    # pile-on stays recoverable.
    hidden = False
    if distinct_reports >= AUTO_HIDE_REPORT_COUNT and image.moderation_status == MOD_APPROVED:
        image.moderation_status = MOD_PENDING_REVIEW
        image.moderation_reason = "user_reported"
        image.is_approved = False
        image.is_primary = False
        image.visibility_status = VISIBILITY_HIDDEN
        hidden = True
        logger.warning(
            "image_auto_hidden_by_reports image_id=%s reports=%s",
            image_id, distinct_reports,
        )

    db.commit()
    return {"status": "reported", "withheld": hidden}


class QueueItem(BaseModel):
    image_id: str
    place_id: str
    url: Optional[str]
    moderation_status: str
    moderation_reason: Optional[str]
    quality_score: Optional[float]
    blur_score: Optional[float]
    gps_verified: bool
    safety_scanned: bool
    uploaded_by: Optional[str]
    report_count: int


@router.get("/queue", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def review_queue(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
):
    images = (
        db.query(PlaceImage)
        .filter(PlaceImage.moderation_status == MOD_PENDING_REVIEW)
        .order_by(PlaceImage.created_at.asc())
        .limit(limit)
        .all()
    )

    if not images:
        return {"queue": []}

    image_ids = [i.id for i in images]
    counts = dict(
        db.query(ImageReport.image_id, func.count(ImageReport.id))
        .filter(ImageReport.image_id.in_(image_ids))
        .group_by(ImageReport.image_id)
        .all()
    )

    return {
        "queue": [
            QueueItem(
                image_id=i.id,
                place_id=i.place_id,
                url=i.url,
                moderation_status=i.moderation_status,
                moderation_reason=i.moderation_reason,
                quality_score=i.quality_score,
                blur_score=i.blur_score,
                gps_verified=bool(i.gps_verified),
                safety_scanned=bool(i.safety_scanned),
                uploaded_by=i.uploaded_by,
                report_count=counts.get(i.id, 0),
            )
            for i in images
        ]
    }


@router.post(
    "/images/{image_id}/review",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def review_image(
    image_id: str,
    payload: ReviewRequest = Body(...),
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    if payload.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be approve or reject")

    image = db.query(PlaceImage).filter(PlaceImage.id == image_id).one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="image not found")

    image.reviewed_at = datetime.now(timezone.utc)
    image.reviewed_by = admin_id

    if payload.decision == "approve":
        image.moderation_status = MOD_APPROVED
        image.is_approved = True
        image.moderation_reason = None
        # Deliberately not restored to primary/showcase here. Approval
        # means "allowed to be seen", not "should be the face of this
        # place" — the invariant service elects primaries on quality, and
        # forcing one here would override it.
        image.visibility_status = VISIBILITY_GALLERY_ONLY
    else:
        image.moderation_status = MOD_REJECTED
        image.is_approved = False
        image.is_primary = False
        image.visibility_status = VISIBILITY_HIDDEN
        image.moderation_reason = image.moderation_reason or "manual_reject"

    db.commit()

    # Re-elect a primary if this decision changed what's eligible.
    try:
        PlaceImageInvariantService().repair(db=db, place_id=image.place_id)
    except Exception:
        logger.exception("moderation_invariant_repair_failed place_id=%s", image.place_id)

    return {"status": image.moderation_status}


# -------------------------
# Video reports + review queue. Same shape as the image endpoints above --
# see place_video.py's moderation_status/moderation_reason comment for how
# this is kept separate from PlaceVideo.status (the processing-pipeline
# lifecycle). No invariant-repair step here: unlike PlaceImage, PlaceVideo
# has no primary/showcase election to re-run after a review decision.
# -------------------------

class VideoReportRequest(BaseModel):
    reason: str = Field(..., description="One of: " + ", ".join(sorted(VALID_VIDEO_REPORT_REASONS)))
    note: Optional[str] = Field(None, max_length=500)


@router.post(
    "/videos/{video_id}/report",
    status_code=201,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def report_video(
    video_id: str,
    payload: VideoReportRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if payload.reason not in VALID_VIDEO_REPORT_REASONS:
        raise HTTPException(status_code=400, detail="invalid reason")

    video = db.query(PlaceVideo).filter(PlaceVideo.id == video_id).one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="video not found")

    report = VideoReport(
        video_id=video_id,
        reporter_id=user_id,
        reason=payload.reason,
        note=(payload.note or "").strip() or None,
    )
    db.add(report)
    try:
        db.flush()
    except IntegrityError:
        # Already reported by this user — idempotent, not an error worth
        # showing them.
        db.rollback()
        return {"status": "already_reported"}

    distinct_reports = (
        db.query(VideoReport.id).filter(VideoReport.video_id == video_id).count()
    )

    # Enough independent people flagged it that leaving it live is the
    # riskier bet. Held for review, never deleted — a coordinated bad-faith
    # pile-on stays recoverable.
    hidden = False
    if (
        distinct_reports >= VIDEO_AUTO_HIDE_REPORT_COUNT
        and video.moderation_status == VIDEO_MOD_APPROVED
    ):
        video.moderation_status = VIDEO_MOD_PENDING_REVIEW
        video.moderation_reason = "user_reported"
        hidden = True
        logger.warning(
            "video_auto_hidden_by_reports video_id=%s reports=%s",
            video_id, distinct_reports,
        )

    db.commit()
    return {"status": "reported", "withheld": hidden}


class VideoQueueItem(BaseModel):
    video_id: str
    place_id: str
    video_url: Optional[str]
    thumbnail_url: Optional[str]
    moderation_status: str
    moderation_reason: Optional[str]
    food_score: Optional[float]
    uploaded_by: str
    report_count: int


@router.get("/videos/queue", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def video_review_queue(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
):
    videos = (
        db.query(PlaceVideo)
        .filter(PlaceVideo.moderation_status == VIDEO_MOD_PENDING_REVIEW)
        .order_by(PlaceVideo.created_at.asc())
        .limit(limit)
        .all()
    )

    if not videos:
        return {"queue": []}

    video_ids = [v.id for v in videos]
    counts = dict(
        db.query(VideoReport.video_id, func.count(VideoReport.id))
        .filter(VideoReport.video_id.in_(video_ids))
        .group_by(VideoReport.video_id)
        .all()
    )

    return {
        "queue": [
            VideoQueueItem(
                video_id=v.id,
                place_id=v.place_id,
                video_url=generate_public_url(v.processed_key) if v.processed_key else None,
                thumbnail_url=generate_public_url(v.thumb_key) if v.thumb_key else None,
                moderation_status=v.moderation_status,
                moderation_reason=v.moderation_reason,
                food_score=v.food_score,
                uploaded_by=v.uploaded_by,
                report_count=counts.get(v.id, 0),
            )
            for v in videos
        ]
    }


@router.post(
    "/videos/{video_id}/review",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def review_video(
    video_id: str,
    payload: ReviewRequest = Body(...),
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    if payload.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be approve or reject")

    video = db.query(PlaceVideo).filter(PlaceVideo.id == video_id).one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="video not found")

    video.reviewed_at = datetime.now(timezone.utc)
    video.reviewed_by = admin_id

    if payload.decision == "approve":
        video.moderation_status = VIDEO_MOD_APPROVED
        video.moderation_reason = None
    else:
        video.moderation_status = VIDEO_MOD_REJECTED
        video.moderation_reason = video.moderation_reason or "manual_reject"

    db.commit()
    return {"status": video.moderation_status}
