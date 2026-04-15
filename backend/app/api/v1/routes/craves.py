"""
Craves list endpoint.

Returns the latest CraveItem records (max 50, descending by created_at).
These are user-submitted URLs that have been processed by the share_parser_worker.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.crave_item import CraveItem

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

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CraveItemOut])
def list_craves(db: Session = Depends(get_db)) -> list[CraveItemOut]:
    """
    Return the latest 50 CraveItems ordered by created_at descending.
    """
    items = (
        db.query(CraveItem)
        .order_by(CraveItem.created_at.desc())
        .limit(50)
        .all()
    )

    return [
        CraveItemOut(
            id=item.id,
            url=item.url,
            source_type=item.source_type,
            parsed_place_name=item.parsed_place_name,
            matched_place_id=item.matched_place_id,
            match_confidence=item.match_confidence,
            status=item.status,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]
