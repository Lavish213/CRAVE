from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.dedup.dedup_scorer import score_place_pair, is_auto_merge, is_review_candidate


logger = logging.getLogger(__name__)

# ~2km bounding box in degrees
_GEO_TOLERANCE = 0.02


@dataclass
class DuplicatePair:
    place_a_id: str
    place_b_id: str
    score: float
    auto_merge: bool
    review: bool
    name_a: str = ""
    name_b: str = ""


@dataclass
class DedupReport:
    city_id: str
    total_checked: int = 0
    pairs_found: int = 0
    auto_merge_pairs: int = 0
    review_pairs: int = 0
    pairs: List[DuplicatePair] = field(default_factory=list)


def find_duplicates_in_city(
    db: Session,
    city_id: str,
    *,
    active_only: bool = True,
) -> DedupReport:
    """
    Find potential duplicate places within a city.

    Uses geo-bounded candidate search to avoid O(n²) full comparisons.
    Returns a DedupReport with all candidate pairs sorted by score desc.
    """

    report = DedupReport(city_id=city_id)
    seen_pairs: set = set()

    stmt = select(Place).where(Place.city_id == city_id)
    if active_only:
        stmt = stmt.where(Place.is_active.is_(True))

    places = list(db.execute(stmt).scalars().all())
    report.total_checked = len(places)

    for place_a in places:
        if place_a.lat is None or place_a.lng is None:
            continue

        # Geo-bounded candidates to avoid O(n²)
        candidates_stmt = select(Place).where(
            and_(
                Place.city_id == city_id,
                Place.id != place_a.id,
                Place.lat >= place_a.lat - _GEO_TOLERANCE,
                Place.lat <= place_a.lat + _GEO_TOLERANCE,
                Place.lng >= place_a.lng - _GEO_TOLERANCE,
                Place.lng <= place_a.lng + _GEO_TOLERANCE,
            )
        )
        if active_only:
            candidates_stmt = candidates_stmt.where(Place.is_active.is_(True))

        candidates = db.execute(candidates_stmt).scalars().all()

        for place_b in candidates:
            pair_key = tuple(sorted([place_a.id, place_b.id]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            score = score_place_pair(
                name_a=place_a.name,
                name_b=place_b.name,
                addr_a=getattr(place_a, "address", None),
                addr_b=getattr(place_b, "address", None),
                lat_a=place_a.lat,
                lng_a=place_a.lng,
                lat_b=place_b.lat,
                lng_b=place_b.lng,
            )

            if is_auto_merge(score) or is_review_candidate(score):
                pair = DuplicatePair(
                    place_a_id=place_a.id,
                    place_b_id=place_b.id,
                    score=score,
                    auto_merge=is_auto_merge(score),
                    review=is_review_candidate(score),
                    name_a=place_a.name,
                    name_b=place_b.name,
                )
                report.pairs.append(pair)
                report.pairs_found += 1

                if pair.auto_merge:
                    report.auto_merge_pairs += 1
                else:
                    report.review_pairs += 1

    report.pairs.sort(key=lambda p: -p.score)

    logger.info(
        "dedup_scan city=%s checked=%s pairs=%s auto_merge=%s review=%s",
        city_id,
        report.total_checked,
        report.pairs_found,
        report.auto_merge_pairs,
        report.review_pairs,
    )

    return report
