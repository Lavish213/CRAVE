# app/api/v1/routes/menu_submissions.py
"""
Restaurant/user menu self-submission: the path for a menu to enter CRAVE
when no scraper has found one (or as a corroborating source alongside one
that has).

A submission is never trusted directly — it's staged in `menu_submissions`
pending review, same shape as the image-report queue in moderation.py. On
approval, `user_submission_service.apply_approved_submission` writes each
item as a PlaceClaim and runs it through the exact same
materialize_menu_truth -> MenuPublisher pipeline every scraped source goes
through, so it's scored and merged rather than silently overwriting
whatever else exists for that place.

Reuses moderation.py's ADMIN_USER_IDS allowlist / require_admin dependency
(404, not 403, for non-admins) rather than inventing a second gate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.db.models.place import Place
from app.db.models.menu_submission import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    MenuSubmission,
)
from app.api.v1.routes.moderation import require_admin
from app.services.menu.user_submission_service import apply_approved_submission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["menu-submissions"])
router_moderation = APIRouter(prefix="/moderation", tags=["menu-submissions"])

MAX_ITEMS_PER_SUBMISSION = 200


class MenuItemSubmissionPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    price_cents: Optional[int] = Field(None, ge=0, le=10_000_000)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be blank")
        return v


class MenuSubmissionRequest(BaseModel):
    items: List[MenuItemSubmissionPayload] = Field(..., min_length=1, max_length=MAX_ITEMS_PER_SUBMISSION)


class MenuSubmissionOut(BaseModel):
    id: str
    place_id: str
    status: str
    item_count: int
    created_at: datetime


class ReviewRequest(BaseModel):
    decision: str = Field(..., description="approve | reject")
    rejection_reason: Optional[str] = Field(None, max_length=500)


@router.post(
    "/{place_id}/menu/submit",
    status_code=201,
    response_model=MenuSubmissionOut,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def submit_menu(
    place_id: str,
    payload: MenuSubmissionRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    place = db.query(Place.id).filter(Place.id == place_id).one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="place not found")

    submission = MenuSubmission(
        place_id=place_id,
        submitted_by=user_id,
        items=[item.model_dump() for item in payload.items],
        status=STATUS_PENDING,
    )
    db.add(submission)
    db.commit()

    return MenuSubmissionOut(
        id=submission.id,
        place_id=submission.place_id,
        status=submission.status,
        item_count=len(submission.items),
        created_at=submission.created_at,
    )


@router_moderation.get(
    "/menu-submissions",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def review_queue(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
):
    submissions = (
        db.query(MenuSubmission)
        .filter(MenuSubmission.status == STATUS_PENDING)
        .order_by(MenuSubmission.created_at.asc())
        .limit(limit)
        .all()
    )

    return {
        "queue": [
            MenuSubmissionOut(
                id=s.id,
                place_id=s.place_id,
                status=s.status,
                item_count=len(s.items or []),
                created_at=s.created_at,
            )
            for s in submissions
        ]
    }


@router_moderation.get(
    "/menu-submissions/{submission_id}",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def get_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    submission = (
        db.query(MenuSubmission).filter(MenuSubmission.id == submission_id).one_or_none()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")

    return {
        "id": submission.id,
        "place_id": submission.place_id,
        "submitted_by": submission.submitted_by,
        "status": submission.status,
        "items": submission.items,
        "created_at": submission.created_at,
        "reviewed_by": submission.reviewed_by,
        "reviewed_at": submission.reviewed_at,
        "rejection_reason": submission.rejection_reason,
    }


@router_moderation.post(
    "/menu-submissions/{submission_id}/review",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def review_submission(
    submission_id: str,
    payload: ReviewRequest = Body(...),
    db: Session = Depends(get_db),
    admin_id: str = Depends(require_admin),
):
    if payload.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be approve or reject")

    submission = (
        db.query(MenuSubmission).filter(MenuSubmission.id == submission_id).one_or_none()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")

    if submission.status != STATUS_PENDING:
        raise HTTPException(status_code=409, detail="submission already reviewed")

    submission.reviewed_at = datetime.now(timezone.utc)
    submission.reviewed_by = admin_id

    if payload.decision == "approve":
        submission.status = STATUS_APPROVED
        db.commit()
        try:
            published_count = apply_approved_submission(db=db, submission=submission)
        except Exception:
            logger.exception(
                "menu_submission_apply_failed submission_id=%s", submission_id
            )
            published_count = 0
        return {"status": submission.status, "published_items": published_count}

    submission.status = STATUS_REJECTED
    submission.rejection_reason = (payload.rejection_reason or "").strip() or None
    db.commit()
    return {"status": submission.status}
