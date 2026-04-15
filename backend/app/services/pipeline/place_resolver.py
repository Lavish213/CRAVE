from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models.place import Place
from app.db.models.city import City
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.pipeline.candidate_normalizer import NormalizedCandidate

logger = logging.getLogger(__name__)

# Geo proximity threshold in degrees (~200m)
GEO_THRESHOLD = 0.002

# Fuzzy name match threshold (0–100)
FUZZY_THRESHOLD = 85

try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    logger.info("rapidfuzz not installed — using exact name matching only")


@dataclass
class ResolvedCandidate:
    candidate: NormalizedCandidate
    place_id: Optional[str]  # None = unresolved → goes to DiscoveryCandidate
    match_method: str  # "exact_name_geo" | "fuzzy_name_geo" | "url_match" | "unresolved"
    match_score: float  # 0.0–1.0


def resolve(db: Session, candidate: NormalizedCandidate) -> ResolvedCandidate:
    """
    Try to match a normalized candidate to an existing Place.
    Returns ResolvedCandidate with place_id set (matched) or None (unresolved).
    """
    place_id, method, score = _try_resolve(db, candidate)

    if place_id:
        logger.debug(
            "candidate_resolved name=%s place_id=%s method=%s score=%.2f",
            candidate.name, place_id, method, score,
        )
    else:
        logger.debug("candidate_unresolved name=%s", candidate.name)

    return ResolvedCandidate(
        candidate=candidate,
        place_id=place_id,
        match_method=method,
        match_score=score,
    )


def resolve_batch(db: Session, candidates: list[NormalizedCandidate]) -> list[ResolvedCandidate]:
    return [resolve(db, c) for c in candidates]


def write_unresolved_to_discovery(db: Session, resolved: ResolvedCandidate) -> Optional[str]:
    """
    Write an unresolved candidate into DiscoveryCandidate staging table.
    Idempotent — skips if external_id already exists.
    Returns new candidate id or None if skipped.

    NOTE: DiscoveryCandidate field mapping:
    - source_platform → stored in `source` column
    - confidence       → stored in `confidence_score` column
    - source_url       → stored in `website` column (model has no source_url field)
    - status default   → "candidate" (model default, not "raw")
    - city_id          → required non-nullable; skips write if city cannot be resolved
    """
    if resolved.place_id:
        return None  # already resolved, don't write to discovery

    c = resolved.candidate

    # Dedup check on website (source_url) if present
    if c.source_url:
        existing = db.execute(
            select(DiscoveryCandidate).where(DiscoveryCandidate.website == c.source_url)
        ).scalar_one_or_none()
        if existing:
            return None

    # Dedup check on external_id + source
    if c.external_id:
        existing = db.execute(
            select(DiscoveryCandidate).where(
                DiscoveryCandidate.external_id == c.external_id,
                DiscoveryCandidate.source == c.source_platform,
            )
        ).scalar_one_or_none()
        if existing:
            return None

    # city_id is non-nullable — skip write if we can't resolve it
    city_id = _resolve_city_id(db, c.city_hint) if c.city_hint else None
    if not city_id:
        logger.debug(
            "discovery_write_skipped_no_city name=%s city_hint=%s",
            c.name, c.city_hint,
        )
        return None

    candidate = DiscoveryCandidate(
        name=c.name,
        lat=c.lat,
        lng=c.lng,
        city_id=city_id,
        source=c.source_platform,          # DiscoveryCandidate.source, not source_platform
        website=c.source_url,              # closest available field for source_url
        external_id=c.external_id,
        confidence_score=c.confidence,     # DiscoveryCandidate.confidence_score
        status="candidate",                # model default; "raw" is not a valid enum value
        resolved=False,
        blocked=False,
    )
    db.add(candidate)
    db.flush()
    logger.debug("discovery_candidate_created name=%s id=%s", c.name, candidate.id)
    return candidate.id


# ---------------------------------------------------------
# Internal resolution logic
# ---------------------------------------------------------

def _try_resolve(
    db: Session, c: NormalizedCandidate
) -> tuple[Optional[str], str, float]:

    # 1. URL-based match (highest confidence)
    if c.source_url:
        place_id = _match_by_url(db, c.source_url)
        if place_id:
            return place_id, "url_match", 1.0

    # 2. Name + geo match
    if c.lat and c.lng:
        place_id, method, score = _match_by_name_geo(db, c)
        if place_id:
            return place_id, method, score

    # 3. Name + city (no geo)
    if c.city_hint:
        place_id, score = _match_by_name_city(db, c)
        if place_id:
            return place_id, "name_city", score

    return None, "unresolved", 0.0


def _match_by_url(db: Session, url: str) -> Optional[str]:
    result = db.execute(
        select(Place.id).where(
            (Place.grubhub_url == url) | (Place.website == url) | (Place.menu_source_url == url)
        )
    ).scalar_one_or_none()
    return result


def _match_by_name_geo(
    db: Session, c: NormalizedCandidate
) -> tuple[Optional[str], str, float]:
    # Fetch nearby places (bounding box)
    nearby = db.execute(
        select(Place).where(
            Place.is_active.is_(True),
            Place.lat.between(c.lat - GEO_THRESHOLD, c.lat + GEO_THRESHOLD),
            Place.lng.between(c.lng - GEO_THRESHOLD, c.lng + GEO_THRESHOLD),
        )
    ).scalars().all()

    if not nearby:
        return None, "unresolved", 0.0

    candidate_name_lower = c.name.lower().strip()

    # Exact match first
    for p in nearby:
        if p.name.lower().strip() == candidate_name_lower:
            return p.id, "exact_name_geo", 1.0

    # Fuzzy match
    if _HAS_RAPIDFUZZ:
        best_place = None
        best_score = 0
        for p in nearby:
            score = _fuzz.token_sort_ratio(c.name, p.name)
            if score > best_score:
                best_score = score
                best_place = p
        if best_place and best_score >= FUZZY_THRESHOLD:
            return best_place.id, "fuzzy_name_geo", best_score / 100.0

    return None, "unresolved", 0.0


def _match_by_name_city(
    db: Session, c: NormalizedCandidate
) -> tuple[Optional[str], float]:
    city_id = _resolve_city_id(db, c.city_hint)
    if not city_id:
        return None, 0.0

    places = db.execute(
        select(Place).where(
            Place.is_active.is_(True),
            Place.city_id == city_id,
        )
    ).scalars().all()

    candidate_lower = c.name.lower().strip()
    for p in places:
        if p.name.lower().strip() == candidate_lower:
            return p.id, 1.0

    return None, 0.0


def _resolve_city_id(db: Session, city_hint: str) -> Optional[str]:
    city_hint_lower = city_hint.lower().strip()
    cities = db.execute(select(City)).scalars().all()
    for city in cities:
        if city_hint_lower in city.name.lower() or city_hint_lower in city.slug.lower():
            return city.id
    return None
