from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.category import Category
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place_claim import PlaceClaim
from app.services.truth.claim_normalizer_v2 import normalize_claim
from app.services.truth.truth_resolver_v2 import resolve_place_truths_v2


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def promote_candidate_v2(
    *,
    db: Session,
    candidate_id: str,
) -> Optional[str]:
    """
    Deterministic V2 Promotion Flow

    - Safe if candidate missing
    - Idempotent
    - Deterministic Place UUID
    - Attaches categories
    - Emits initial claims
    - Resolves truths
    - Updates candidate lifecycle
    """

    candidate: Optional[DiscoveryCandidate] = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.id == candidate_id)
        .one_or_none()
    )

    if not candidate:
        return None

    # Already promoted → ensure truths resolved and exit
    if candidate.resolved_place_id:
        resolve_place_truths_v2(db=db, place_id=candidate.resolved_place_id)
        return candidate.resolved_place_id

    if not candidate.city_id:
        return None

    # Deterministic Place creation
    place = (
        db.query(Place)
        .filter(
            Place.city_id == candidate.city_id,
            Place.name == candidate.name,
        )
        .one_or_none()
    )

    if not place:
        place = Place(
            name=candidate.name,
            city_id=candidate.city_id,
            lat=candidate.lat,
            lng=candidate.lng,
            price_tier=None,
            address=candidate.address,
            website=candidate.website,
        )
        db.add(place)
        db.flush()
    else:
        # Backfill address/website if place exists but fields are empty
        if not place.address and candidate.address:
            place.address = candidate.address
        if not place.website and candidate.website:
            place.website = candidate.website

    # Attach categories (if candidate.category_id exists)
    if getattr(candidate, "category_id", None):
        category = (
            db.query(Category)
            .filter(Category.id == candidate.category_id)
            .one_or_none()
        )
        if category and category not in place.categories:
            place.categories.append(category)

    # Emit core claims (name + geo)
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

    if candidate.lat is not None:
        core_claims.append(
            normalize_claim(
                field="lat",
                value=candidate.lat,
                source="promotion",
                confidence=1.0,
                weight=1.0,
            )
        )

    if candidate.lng is not None:
        core_claims.append(
            normalize_claim(
                field="lng",
                value=candidate.lng,
                source="promotion",
                confidence=1.0,
                weight=1.0,
            )
        )

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
                    **c,
                )
            )

    db.flush()

    # Resolve truths after claim emission
    resolve_place_truths_v2(db=db, place_id=place.id)

    # Update candidate lifecycle
    candidate.resolved = True
    candidate.resolved_place_id = place.id
    candidate.status = "promoted"
    candidate.promoted_at = _utcnow()

    db.flush()

    return place.id