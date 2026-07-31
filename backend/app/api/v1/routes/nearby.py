"""
Live GPS-based "find and add spots" flow.

Concept: a user standing at a real place searches Google Places for exactly
their location (tight radius, no grid scan) instead of the backend's
scheduled city-wide sweep. If CRAVE already has the place, they're pointed
at it directly. If not, confirming it feeds the same discovery-candidate
pipeline every other "user found a place" input uses (unmatched social
shares, hitlist suggestions) — see app/services/discovery/discovery_service.py
and app/services/discovery/promotion_orchestrator_v2.py. One person confirming
a spot isn't enough to add it on its own; it needs to be corroborated (by
another GPS confirmation, a share, or a suggestion) before the scheduler's
discovery job (runs every 5 minutes) promotes it to a real Place.

No new credentials needed — reuses GOOGLE_PLACES_API_KEY, same as the
scheduled Google Places ingest.
"""
from __future__ import annotations

import math
import os
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.db.models.place import Place
from app.services.ingest.google_places_ingest import GooglePlacesIngest
from app.services.discovery.discovery_service import ingest_candidate_v2

router = APIRouter(prefix="/nearby", tags=["nearby"])

SEARCH_RADIUS_M = 150

# A confirmed GPS spot is close enough to an existing Place to be treated as
# "already in CRAVE" within this radius — loose enough to absorb GPS drift,
# tight enough not to conflate two different restaurants in the same block.
ALREADY_LISTED_RADIUS_M = 60

# Confidence assigned to a DiscoveryCandidate from a single user's GPS
# confirmation — see UNMATCHED_SHARE_CANDIDATE_CONFIDENCE (0.3) and
# HITLIST_SUGGESTION_CANDIDATE_CONFIDENCE (0.4) for the other two inputs
# feeding the same pipeline. A GPS confirmation is stronger evidence than a
# scraped caption (the person is standing there) but still just one signal.
GPS_CANDIDATE_CONFIDENCE = 0.35


def _meters_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Equirectangular approximation — accurate enough at this scale (<1km)."""
    deg_to_m = 111_320.0
    dlat = (lat2 - lat1) * deg_to_m
    dlng = (lng2 - lng1) * deg_to_m * math.cos(math.radians(lat1))
    return math.sqrt(dlat ** 2 + dlng ** 2)


class NearbySearchRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class NearbyCandidateOut(BaseModel):
    external_id: Optional[str]
    name: str
    address: Optional[str]
    lat: float
    lng: float
    category_hint: Optional[str]
    distance_m: float
    already_in_crave: bool
    place_id: Optional[str] = None


class NearbySearchResponse(BaseModel):
    results: List[NearbyCandidateOut]


class NearbyConfirmRequest(BaseModel):
    external_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=160)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None
    category_hint: Optional[str] = None


class NearbyConfirmResponse(BaseModel):
    status: str
    candidate_id: str
    confidence_score: float


@router.post("/search", response_model=NearbySearchResponse, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def search_nearby(
    payload: NearbySearchRequest = Body(...),
    db: Session = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
):
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Nearby search is not configured")

    client = GooglePlacesIngest(api_key=api_key)
    raw_results = client.search_nearby(lat=payload.lat, lng=payload.lng, radius_m=SEARCH_RADIUS_M)

    # Cross-reference against existing Places within a loose bounding box —
    # cheap pre-filter before the precise distance check.
    deg_pad = (SEARCH_RADIUS_M + ALREADY_LISTED_RADIUS_M) / 111_320.0
    nearby_places = (
        db.query(Place)
        .filter(
            Place.is_active.is_(True),
            Place.lat.between(payload.lat - deg_pad, payload.lat + deg_pad),
            Place.lng.between(payload.lng - deg_pad, payload.lng + deg_pad),
        )
        .all()
    )

    out: List[NearbyCandidateOut] = []
    for r in raw_results:
        lat, lng = r.get("lat"), r.get("lng")
        if lat is None or lng is None:
            continue

        distance = _meters_between(payload.lat, payload.lng, lat, lng)

        matched_place_id: Optional[str] = None
        for p in nearby_places:
            if p.lat is None or p.lng is None:
                continue
            if _meters_between(lat, lng, p.lat, p.lng) <= ALREADY_LISTED_RADIUS_M:
                matched_place_id = p.id
                break

        out.append(
            NearbyCandidateOut(
                external_id=r.get("external_id"),
                name=r.get("name"),
                address=r.get("address"),
                lat=lat,
                lng=lng,
                category_hint=r.get("category_hint"),
                distance_m=round(distance, 1),
                already_in_crave=matched_place_id is not None,
                place_id=matched_place_id,
            )
        )

    out.sort(key=lambda c: c.distance_m)
    return NearbySearchResponse(results=out)


@router.post("/confirm", response_model=NearbyConfirmResponse, status_code=201, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def confirm_new_spot(
    payload: NearbyConfirmRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        candidate = ingest_candidate_v2(
            db=db,
            name=payload.name,
            lat=payload.lat,
            lng=payload.lng,
            address=payload.address,
            source="user_gps",
            external_id=payload.external_id,
            category_hint=payload.category_hint,
            confidence=GPS_CANDIDATE_CONFIDENCE,
            raw_payload={"confirmed_by": user_id},
            contributor_key=f"user_gps:{user_id}",
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return NearbyConfirmResponse(
        status="candidate_recorded",
        candidate_id=candidate.id,
        confidence_score=candidate.confidence_score,
    )
