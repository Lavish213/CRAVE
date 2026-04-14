from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.place import Place


logger = logging.getLogger(__name__)


MAX_DISTANCE_METERS = 150
HARD_MATCH_THRESHOLD = 0.85
SOFT_MATCH_THRESHOLD = 0.75


@dataclass
class MatchResult:
    matched: bool
    score: float
    reason: str
    provider_id: Optional[str] = None
    provider_url: Optional[str] = None


def match_place(
    *,
    local_place,
    provider_places: List[dict],
) -> MatchResult:

    if not local_place or not provider_places:
        return MatchResult(False, 0.0, "no_input")

    best_score = 0.0
    best_candidate: Optional[dict] = None

    for candidate in provider_places:

        candidate_name = candidate.get("name")
        candidate_lat = candidate.get("lat")
        candidate_lng = candidate.get("lng")

        if not candidate_name:
            continue

        name_score = _name_similarity(
            local_place.name,
            candidate_name,
        )

        if name_score < 0.4:
            continue

        distance = _distance_meters(
            local_place.lat,
            local_place.lng,
            candidate_lat,
            candidate_lng,
        )

        distance_score = _distance_score(distance)

        score = (name_score * 0.7) + (distance_score * 0.3)

        if score > best_score:
            best_score = score
            best_candidate = candidate

        if score >= HARD_MATCH_THRESHOLD:
            break

    if not best_candidate:
        return MatchResult(False, 0.0, "no_candidates")

    if best_score >= HARD_MATCH_THRESHOLD:
        reason = "high_confidence"
        matched = True
    elif best_score >= SOFT_MATCH_THRESHOLD:
        reason = "medium_confidence"
        matched = True
    else:
        reason = "low_confidence"
        matched = False

    return MatchResult(
        matched=matched,
        score=best_score,
        reason=reason,
        provider_id=str(best_candidate.get("id")),
        provider_url=best_candidate.get("url"),
    )


_GEO_DEGREE_TOLERANCE = 0.02   # ~2 km bounding box


def match_or_create_place(
    *,
    db: Session,
    name: str,
    lat: float | None = None,
    lng: float | None = None,
    address: str | None = None,
) -> str:

    if not name:
        raise ValueError("name required")

    # Geo-bounded query to avoid full-table scan (N+1 fix).
    # Falls back to city-agnostic name query when no coordinates provided.
    from sqlalchemy import select, and_

    if lat is not None and lng is not None:
        stmt = select(Place).where(
            and_(
                Place.lat >= lat - _GEO_DEGREE_TOLERANCE,
                Place.lat <= lat + _GEO_DEGREE_TOLERANCE,
                Place.lng >= lng - _GEO_DEGREE_TOLERANCE,
                Place.lng <= lng + _GEO_DEGREE_TOLERANCE,
            )
        )
        local_places = list(db.execute(stmt).scalars().all())
    else:
        stmt = select(Place).where(Place.name.ilike(f"%{name}%")).limit(200)
        local_places = list(db.execute(stmt).scalars().all())

    provider_candidates = [
        {
            "id": p.id,
            "name": p.name,
            "lat": p.lat,
            "lng": p.lng,
            "url": p.website,
        }
        for p in local_places
    ]

    temp_place = type(
        "TempPlace",
        (),
        {"name": name, "lat": lat, "lng": lng},
    )()

    result = match_place(
        local_place=temp_place,
        provider_places=provider_candidates,
    )

    if result.matched and result.provider_id:
        return result.provider_id

    new_place = Place(
        name=name,
        city_id="745fa4ed-9309-54a3-97b3-717717a5f05b",
        lat=lat,
        lng=lng,
        website=None,
    )

    db.add(new_place)
    db.flush()

    return new_place.id


def _name_similarity(a: str, b: str) -> float:

    if not a or not b:
        return 0.0

    a_norm = _normalize(a)
    b_norm = _normalize(b)

    if a_norm == b_norm:
        return 1.0

    if not a_norm or not b_norm:
        return 0.0

    # SequenceMatcher catches partial overlaps that Jaccard misses
    seq_score = SequenceMatcher(None, a_norm, b_norm).ratio()

    # Jaccard token score
    tokens_a = set(a_norm.split())
    tokens_b = set(b_norm.split())

    if tokens_a and tokens_b:
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union)
    else:
        jaccard = 0.0

    # Blend: SequenceMatcher is the primary signal
    base_score = (seq_score * 0.6) + (jaccard * 0.4)

    if a_norm in b_norm or b_norm in a_norm:
        base_score = min(base_score + 0.1, 1.0)

    return min(base_score, 1.0)


def _normalize(text: str) -> str:

    text = text.lower().strip()

    for char in [".", ",", "'", "&", "-", "_", "(", ")", "/"]:
        text = text.replace(char, " ")

    text = " ".join(text.split())

    for word in ["restaurant", "cafe", "grill", "kitchen", "bar"]:
        text = text.replace(word, "")

    return " ".join(text.split())


def _distance_meters(lat1, lon1, lat2, lon2) -> float:

    if None in (lat1, lon1, lat2, lon2):
        return 99999

    try:
        R = 6371000

        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))

        dphi = math.radians(float(lat2) - float(lat1))
        dlambda = math.radians(float(lon2) - float(lon1))

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )

        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    except Exception:
        return 99999


def _distance_score(distance: float) -> float:

    if distance <= 20:
        return 1.0
    if distance <= 50:
        return 0.9
    if distance <= 100:
        return 0.75
    if distance <= MAX_DISTANCE_METERS:
        return 0.5
    return 0.0