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

GET /craves/reasoned — the Craves Screen Contract's "reasoned subset"
(docs/doctrine/CRAVE_SCREEN_CONTRACT_CRAVES.md §5/§6): the same
recommendation engine as Decision Session (build_decision_session),
scoped to this user's saved pool instead of a city/radius fetch. See
that function's own module docstring for the role-selection logic
itself -- this route only owns candidate retrieval and graduation.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.crave_item import CraveItem
from app.db.models.hitlist_save import HitlistSave
from app.db.models.place import Place
from app.db.models.visit_evidence import VisitEvidence
from app.core.auth import require_api_key
from app.core.user_auth import get_current_user_id
from app.core.rate_limit import rate_limit
from app.services.decision_session.decision_session_builder import build_decision_session
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.query.place_video_visibility_query import get_has_video_bulk
from app.services.query.rank_percentile_query import get_rank_percentiles
from app.api.v1.schemas.decision_session import DecisionSessionCardOut, DecisionSessionOut
from app.api.v1.schemas.places import PlaceOut

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


@router.get(
    "/reasoned",
    response_model=DecisionSessionOut,
    dependencies=[Depends(rate_limit)],
)
def get_craves_reasoned(
    lat: Optional[float] = Query(None, description="User latitude"),
    lng: Optional[float] = Query(None, description="User longitude"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
) -> DecisionSessionOut:
    """
    Craves Screen Contract §9: native saves and manually-added entries
    (both live in HitlistSave) and matched imported/social-matched
    CraveItems reconcile to two evidence types feeding this one
    contract identically -- their origin/provenance differs only for
    correction/retraction purposes, never for scoring.
    """
    hitlist_place_ids = {
        row[0]
        for row in db.query(HitlistSave.place_id).filter(
            HitlistSave.user_id == user_id,
            HitlistSave.place_id.isnot(None),
        )
    }
    crave_place_ids = {
        row[0]
        for row in db.query(CraveItem.matched_place_id).filter(
            CraveItem.submitted_by == user_id,
            CraveItem.matched_place_id.isnot(None),
        )
    }
    candidate_ids = hitlist_place_ids | crave_place_ids
    if not candidate_ids:
        return DecisionSessionOut(cards=[], degraded=True)

    # Graduation (contract §10): any visit-evidence tier at all -- declared,
    # verified, or inferred -- removes a place from the active pool. Looser
    # than Rank Home's declared/verified-only bar, so this reads
    # VisitEvidence directly rather than HitlistSave.visited, which is only
    # ever set for native saves (dedup_key "save:") and never for
    # craves-discovery rows -- see HitlistSave's own field comment.
    graduated_ids = {
        row[0]
        for row in db.query(VisitEvidence.place_id).filter(
            VisitEvidence.user_id == user_id,
            VisitEvidence.place_id.in_(candidate_ids),
        ).distinct()
    }
    active_candidate_ids = candidate_ids - graduated_ids
    if not active_candidate_ids:
        return DecisionSessionOut(cards=[], degraded=True)

    try:
        candidates = (
            db.query(Place)
            .filter(Place.id.in_(active_candidate_ids), Place.is_active.is_(True))
            .all()
        )
    except Exception as exc:
        logger.exception("craves_reasoned_query_failed user_id=%s error=%s", user_id, exc)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    if not candidates:
        return DecisionSessionOut(cards=[], degraded=True)

    place_ids = [p.id for p in candidates]
    rank_percentiles = get_rank_percentiles(db, place_ids=place_ids)

    built_cards = build_decision_session(candidates, rank_percentiles=rank_percentiles, lat=lat, lng=lng)

    image_urls = get_primary_image_urls_bulk(db, place_ids=[c.place.id for c in built_cards])
    video_flags = get_has_video_bulk(db, place_ids=[c.place.id for c in built_cards])

    cards = []
    for c in built_cards:
        try:
            c.place.primary_image_url = image_urls.get(c.place.id)
            c.place.has_video = video_flags.get(c.place.id, False)
            c.place.rank_percentile = rank_percentiles.get(c.place.id)
            cards.append(
                DecisionSessionCardOut(
                    place=PlaceOut.model_validate(c.place, from_attributes=True),
                    role=c.role,
                    reason_codes=c.reason_codes,
                )
            )
        except Exception as exc:
            # Same silent-drop hazard already fixed in places.py/
            # decision_session.py -- a place failing PlaceOut validation
            # must be visible, not just quietly absent from the response.
            logger.exception("craves_reasoned_serialize_failed place_id=%s", getattr(c.place, "id", None))

    logger.info(
        "API_RESPONSE endpoint=/craves/reasoned user_id=%s roles=%s",
        user_id, [c.role for c in cards],
    )

    return DecisionSessionOut(cards=cards, degraded=len(cards) < 3)
