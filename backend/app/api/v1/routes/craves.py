"""
Craves endpoints.

GET /craves — the signed-in user's own submitted CraveItems (max 50, newest
first). Previously this had no auth and no filtering at all — it returned
the latest 50 CraveItems from every user in the system, and the frontend
labeled the section "Craves ... tracked by CRAVE" as if it were personal.
Now it's scoped to the verified token's user id, matching how share.py now
always sets submitted_by from that same token (never client-supplied).

GET /craves/for-place/{place_id} — public. Returns the matched CraveItems
for a given place, so the place-detail screen can show "seen on TikTok"
style social proof with a thumbnail.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.crave_item import CraveItem
from app.core.auth import require_api_key
from app.core.user_auth import get_current_user_id
from app.core.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/craves", tags=["craves"])


class CraveItemOut(BaseModel):
    id: str
    url: str
    source_type: str
    parsed_place_name: Optional[str]
    matched_place_id: Optional[str]
    match_confidence: Optional[float]
    status: str
    created_at: str
    thumbnail_url: Optional[str] = None
    author_name: Optional[str] = None

    # submitted_by intentionally excluded from both endpoints — GET /craves
    # is scoped to the caller already, so echoing it back is redundant, and
    # GET /craves/for-place is public, where it would leak who shared what.
    model_config = {"from_attributes": True}


def _to_out(item: CraveItem) -> CraveItemOut:
    return CraveItemOut(
        id=item.id,
        url=item.url,
        source_type=item.source_type,
        parsed_place_name=item.parsed_place_name,
        matched_place_id=item.matched_place_id,
        match_confidence=item.match_confidence,
        status=item.status,
        created_at=item.created_at.isoformat(),
        thumbnail_url=item.thumbnail_url,
        author_name=item.author_name,
    )


@router.get("", response_model=list[CraveItemOut], dependencies=[Depends(rate_limit)])
def list_craves(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
) -> list[CraveItemOut]:
    """
    Return the caller's own latest 50 CraveItems, ordered by created_at
    descending.
    """
    items = (
        db.query(CraveItem)
        .filter(CraveItem.submitted_by == user_id)
        .order_by(CraveItem.created_at.desc())
        .limit(50)
        .all()
    )

    return [_to_out(item) for item in items]


@router.get(
    "/for-place/{place_id}",
    response_model=list[CraveItemOut],
    dependencies=[Depends(rate_limit)],
)
def list_craves_for_place(place_id: str, db: Session = Depends(get_db)) -> list[CraveItemOut]:
    """
    Return matched CraveItems for a given place — public, no auth, since
    this is social-proof content meant to be shown on the place detail
    screen to any visitor, not just the person who shared it.
    """
    items = (
        db.query(CraveItem)
        .filter(CraveItem.matched_place_id == place_id, CraveItem.status == "matched")
        .order_by(CraveItem.created_at.desc())
        .limit(20)
        .all()
    )

    return [_to_out(item) for item in items]
