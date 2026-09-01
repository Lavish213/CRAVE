"""
Centralized visibility query for "does this place have video" (E3).

Mirrors app.services.query.place_image_visibility_query's shape: a
single bulk lookup, visibility-gated, meant to be called once per
request and merged onto already-loaded Place rows -- never N+1'd per
place.
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place_video import (
    PlaceVideo,
    STATUS_APPROVED,
    MOD_APPROVED,
)


def get_has_video_bulk(db: Session, *, place_ids: List[str]) -> Dict[str, bool]:
    """
    Bulk "has at least one approved, visible video" check for a list of
    place IDs. A video only counts if it passed the processing pipeline
    (status=approved) AND hasn't been pulled by moderation
    (moderation_status=approved) -- the same two-gate visibility rule
    the feed itself uses. Missing keys are implicitly False.

    Returns: {place_id: True} for every place with at least one
    qualifying video. Places with none are simply absent from the dict
    -- callers should use `.get(place_id, False)`.
    """
    if not place_ids:
        return {}

    stmt = (
        select(PlaceVideo.place_id)
        .where(
            PlaceVideo.place_id.in_(place_ids),
            PlaceVideo.status == STATUS_APPROVED,
            PlaceVideo.moderation_status == MOD_APPROVED,
        )
        .distinct()
    )

    return {row[0]: True for row in db.execute(stmt).all()}
