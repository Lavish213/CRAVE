"""
Share-to-CRAVE ingestion endpoint.

Accepts a user-submitted URL (Instagram post, TikTok video, blog article, etc.)
that mentions a restaurant. The URL is stored as a CraveItem with status='pending'
and the share_parser_worker picks it up asynchronously to extract the place name
and attempt a match against the Place catalogue.

Previously this had no auth at all, and the caller could freely set
`submitted_by` to any string — meaning anyone could either impersonate
another user's submissions or leave it blank, so a user's own "Craves"
list could never be reliably scoped to them (GET /craves used to return
the latest 50 items from every user with no filtering). Now requires a
verified session; submitted_by is always the token's user id, never
client-supplied.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.crave_item import CraveItem
from app.core.auth import require_api_key
from app.core.user_auth import get_current_user_id
from app.core.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])

VALID_SOURCE_TYPES = {"instagram", "tiktok", "youtube", "twitter", "web", "other"}

_URL_RE = re.compile(
    r"^https?://"           # scheme
    r"[^\s/$.?#]"           # first char of host — not whitespace
    r"[^\s]*$",             # remainder
    re.IGNORECASE,
)


class ShareIntakeRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048, description="URL of the shared content")
    source_type: str = Field(
        default="web",
        description="Platform hint: instagram | tiktok | youtube | twitter | web | other",
    )

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        v = v.strip()
        if not _URL_RE.match(v):
            raise ValueError("url must be a valid http/https URL")
        return v

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        v = (v or "web").strip().lower()
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type must be one of: {sorted(VALID_SOURCE_TYPES)}"
            )
        return v


class ShareIntakeResponse(BaseModel):
    id: str
    status: str
    message: str


@router.post(
    "",
    response_model=ShareIntakeResponse,
    status_code=202,
    dependencies=[Depends(rate_limit)],
)
def share_intake(
    body: ShareIntakeRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
) -> ShareIntakeResponse:
    """
    Submit a URL that mentions a restaurant.

    The URL is stored immediately with status='pending'. A background worker
    will scrape the page, extract the restaurant name, and attempt to match it
    against CRAVE's place catalogue.

    Returns 202 Accepted — processing happens asynchronously.
    """
    item = CraveItem(
        url=body.url,
        source_type=body.source_type,
        submitted_by=user_id,
    )

    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except Exception as exc:
        db.rollback()
        logger.exception("share_intake_failed url=%s error=%s", body.url, exc)
        raise HTTPException(status_code=500, detail="Failed to store submission")

    logger.info(
        "share_intake_received id=%s source_type=%s has_submitter=%s",
        item.id,
        item.source_type,
        bool(item.submitted_by),
    )

    return ShareIntakeResponse(
        id=item.id,
        status="pending",
        message="Received. We'll process this shortly.",
    )
