from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.category import Category
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place_claim import PlaceClaim
from app.services.discovery.nominatim_client import search_place
from app.services.truth.claim_normalizer_v2 import normalize_claim
from app.services.truth.truth_resolver_v2 import resolve_place_truths_v2


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _geocode_from_candidate(candidate: DiscoveryCandidate) -> tuple[Optional[float], Optional[float]]:
    parts = [candidate.name]
    if candidate.address:
        parts.append(candidate.address)
    query = " ".join(p for p in parts if p)
    if not query:
        return None, None
    try:
        result = search_place(query=query)
        if result and result.get("lat") and result.get("lon"):
            return float(result["lat"]), float(result["lon"])
    except Exception as exc:
        logger.debug("nominatim_geocode_failed candidate_id=%s error=%s", candidate.id, exc)
    return None, None


def promote_candidate_v2(
    *,
    db: Session,
    candidate_id: str,
) -> Optional[str]:

    candidate: Optional[DiscoveryCandidate] = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.id == candidate_id)
        .one_or_none()
    )

    if not candidate:
        return None

    if candidate.resolved_place_id:
        resolve_place_truths_v2(db=db, place_id=candidate.resolved_place_id)
        return candidate.resolved_place_id

    if not candidate.city_id:
        return None

    lat = candidate.lat
    lng = candidate.lng

    if lat is None or lng is None:
        lat, lng = _geocode_from_candidate(candidate)
        if lat is not None and lng is not None:
            candidate.lat = lat
            candidate.lng = lng
            db.flush()
        else:
            logger.debug(
                "promote_skipped_no_coords candidate_id=%s name=%s",
                candidate_id,
                candidate.name,
            )
            return None

    place = (
        db.query(Place)
        .filter(
            Place.city_id == candidate.city_id,
            func.lower(Place.name) == candidate.name.lower(),
        )
        .one_or_none()
    )

    if not place:
        place = Place(
            name=candidate.name,
            city_id=candidate.city_id,
            lat=lat,
            lng=lng,
            price_tier=None,
            address=candidate.address,
            website=candidate.website,
        )
        db.add(place)
        db.flush()
    else:
        if not place.address and candidate.address:
            place.address = candidate.address
        if not place.website and candidate.website:
            place.website = candidate.website
        if place.lat is None and lat is not None:
            place.lat = lat
        if place.lng is None and lng is not None:
            place.lng = lng

    if getattr(candidate, "category_id", None):
        category = (
            db.query(Category)
            .filter(Category.id == candidate.category_id)
            .one_or_none()
        )
        if category and category not in place.categories:
            place.categories.append(category)

    core_claims = []

    core_claims.append(
        normalize_claim(
            field="name",
            value=candidate.name,
            source="promotion",
            confidence=1.0,
            weight=1.0,
            is_verified_source=True,
        )
    )

    core_claims.append(
        normalize_claim(
            field="lat",
            value=lat,
            source="promotion",
            confidence=1.0,
            weight=1.0,
        )
    )

    core_claims.append(
        normalize_claim(
            field="lng",
            value=lng,
            source="promotion",
            confidence=1.0,
            weight=1.0,
        )
    )

    _CLAIM_FIELDS = {
        "field", "value_text", "value_number", "value_json",
        "source", "confidence", "weight", "claim_key",
        "is_user_submitted", "is_verified_source",
    }

    for c in core_claims:
        existing = (
            db.query(PlaceClaim)
            .filter(
                PlaceClaim.place_id == place.id,
                PlaceClaim.field == c["field"],
                PlaceClaim.claim_key == c["claim_key"],
            )
            .one_or_none()
        )
        if not existing:
            db.add(
                PlaceClaim(
                    place_id=place.id,
                    **{k: v for k, v in c.items() if k in _CLAIM_FIELDS},
                )
            )

    db.flush()

    resolve_place_truths_v2(db=db, place_id=place.id)

    candidate.resolved = True
    candidate.resolved_place_id = place.id
    candidate.status = "promoted"
    candidate.promoted_at = _utcnow()

    db.flush()

    return place.id
