from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.truth.score_candidates import score_candidate_group
from app.services.entity.entity_matcher import entity_match


logger = logging.getLogger(__name__)

UTC = timezone.utc
DEFAULT_STATUS = "active"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        v = float(value)

        if math.isnan(v) or math.isinf(v):
            return None

        return v
    except Exception:
        return None


def _clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _normalize_name(value: Any) -> str:
    value = _clean_string(value)
    return value.lower() if value else ""


def _confidence(candidate: Any) -> float:
    value = getattr(candidate, "confidence_score", None)

    try:
        score = float(value)
    except Exception:
        score = 0.0

    if math.isnan(score) or math.isinf(score):
        return 0.0

    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0

    return score


def _candidate_to_claim_like(candidate: DiscoveryCandidate) -> Dict[str, Any]:
    """
    Adapter so we can reuse score_candidate_group safely even if the
    candidate pipeline does not yet emit full PlaceClaim rows.
    """
    payload = candidate.raw_payload if isinstance(candidate.raw_payload, dict) else {}

    dt = getattr(candidate, "updated_at", None) or getattr(candidate, "created_at", None)

    return {
        "candidate": candidate,
        "confidence": _confidence(candidate),
        "weight": 1.0,
        "created_at": getattr(candidate, "created_at", None),
        "value_json": {
            **payload,
            "source_type": payload.get("source_type", "fallback"),
            "ingested_at": dt.isoformat() if dt else None,
        },
        "is_verified_source": False,
        "is_user_submitted": False,
    }


class _ClaimAdapter:
    """
    Lightweight object wrapper so score_candidate_group can use attribute access.
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


def _winner_from_cluster(cluster: List[DiscoveryCandidate]) -> Tuple[DiscoveryCandidate, float]:
    if not cluster:
        raise ValueError("Empty cluster cannot be resolved")

    adapted = [_ClaimAdapter(_candidate_to_claim_like(c)) for c in cluster]
    winner_claim, normalized_confidence = score_candidate_group(adapted)

    if normalized_confidence < 0.0:
        normalized_confidence = 0.0
    if normalized_confidence > 1.0:
        normalized_confidence = 1.0

    return winner_claim.candidate, normalized_confidence


def _best_name(cluster: List[DiscoveryCandidate], winner: DiscoveryCandidate) -> Optional[str]:
    winner_name = _clean_string(getattr(winner, "name", None))
    if winner_name:
        return winner_name

    names: List[str] = []

    for c in cluster:
        name = _clean_string(getattr(c, "name", None))
        if name:
            names.append(name)

    if not names:
        return None

    return max(names, key=lambda x: (len(x), x))


def _best_address(cluster: List[DiscoveryCandidate], winner: DiscoveryCandidate) -> Optional[str]:
    winner_address = _clean_string(getattr(winner, "address", None))
    if winner_address:
        return winner_address

    for c in cluster:
        addr = _clean_string(getattr(c, "address", None))
        if addr:
            return addr

    return None


def _best_phone(cluster: List[DiscoveryCandidate], winner: DiscoveryCandidate) -> Optional[str]:
    winner_phone = _clean_string(getattr(winner, "phone", None))
    if winner_phone:
        return winner_phone

    for c in cluster:
        phone = _clean_string(getattr(c, "phone", None))
        if phone:
            return phone

    return None


def _best_website(cluster: List[DiscoveryCandidate], winner: DiscoveryCandidate) -> Optional[str]:
    winner_website = _clean_string(getattr(winner, "website", None))
    if winner_website:
        return winner_website

    for c in cluster:
        website = _clean_string(getattr(c, "website", None))
        if website:
            return website

    return None


def _best_category_id(cluster: List[DiscoveryCandidate], winner: DiscoveryCandidate) -> Optional[str]:
    winner_category = getattr(winner, "category_id", None)
    if winner_category:
        return winner_category

    for c in cluster:
        category_id = getattr(c, "category_id", None)
        if category_id:
            return category_id

    return None


def _best_city_id(cluster: List[DiscoveryCandidate], winner: DiscoveryCandidate) -> Optional[str]:
    winner_city = getattr(winner, "city_id", None)
    if winner_city:
        return winner_city

    for c in cluster:
        city_id = getattr(c, "city_id", None)
        if city_id:
            return city_id

    return None


def _best_coordinates(
    cluster: List[DiscoveryCandidate],
    winner: DiscoveryCandidate,
) -> Tuple[Optional[float], Optional[float]]:
    lat = _safe_float(getattr(winner, "lat", None))
    lng = _safe_float(getattr(winner, "lng", None))

    if lat is not None and lng is not None:
        return lat, lng

    points = []

    for c in cluster:
        c_lat = _safe_float(getattr(c, "lat", None))
        c_lng = _safe_float(getattr(c, "lng", None))

        if c_lat is not None and c_lng is not None:
            points.append((c_lat, c_lng))

    if not points:
        return None, None

    avg_lat = sum(p[0] for p in points) / len(points)
    avg_lng = sum(p[1] for p in points) / len(points)

    return avg_lat, avg_lng


def _find_existing_place(
    db: Session,
    *,
    name: Optional[str],
    city_id: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
    address: Optional[str] = None,
) -> Optional[Place]:
    if not name or not city_id:
        return None

    stmt = select(Place).where(
        Place.city_id == city_id,
        func.lower(Place.name) == name.lower(),
    )

    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        return existing

    if lat is None or lng is None:
        return None

    nearby_stmt = select(Place).where(
        Place.city_id == city_id,
        Place.lat.is_not(None),
        Place.lng.is_not(None),
    )

    nearby = db.execute(nearby_stmt).scalars().all()

    probe = {
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
    }

    for place in nearby:
        candidate_place = {
            "name": place.name,
            "address": getattr(place, "address", None),
            "lat": getattr(place, "lat", None),
            "lng": getattr(place, "lng", None),
        }

        if entity_match(probe, candidate_place):
            return place

    return None


def _update_place_if_better(
    place: Place,
    *,
    name: str,
    address: Optional[str],
    category_id: Optional[str],
    phone: Optional[str],
    website: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
    normalized_confidence: float,
    now: datetime,
) -> None:
    changed = False

    if name and not getattr(place, "name", None):
        place.name = name
        changed = True

    if address and not getattr(place, "address", None):
        place.address = address
        changed = True

    if category_id and not getattr(place, "category_id", None):
        place.category_id = category_id
        changed = True

    if phone and not getattr(place, "phone", None):
        place.phone = phone
        changed = True

    if website and not getattr(place, "website", None):
        place.website = website
        changed = True

    if lat is not None:
        current_lat = _safe_float(getattr(place, "lat", None))
        if current_lat is None:
            place.lat = lat
            changed = True

    if lng is not None:
        current_lng = _safe_float(getattr(place, "lng", None))
        if current_lng is None:
            place.lng = lng
            changed = True

    if hasattr(place, "confidence_score"):
        existing_conf = _safe_float(getattr(place, "confidence_score", None)) or 0.0
        if normalized_confidence > existing_conf:
            place.confidence_score = normalized_confidence
            changed = True

    if changed and hasattr(place, "updated_at"):
        place.updated_at = now


# ---------------------------------------------------------
# Resolver
# ---------------------------------------------------------

class PlaceResolver:
    """
    Resolves clustered DiscoveryCandidate rows into canonical Place rows.

    Behavior
    --------
    • Selects a winner from each cluster
    • Builds canonical place fields from cluster evidence
    • Upserts into Place
    • Marks candidates resolved
    • Does not destroy useful candidate data
    """

    def resolve_cluster(
        self,
        *,
        db: Session,
        cluster: List[DiscoveryCandidate],
    ) -> Place:
        if not cluster:
            raise ValueError("Cannot resolve empty cluster")

        winner, normalized_confidence = _winner_from_cluster(cluster)

        name = _best_name(cluster, winner)
        city_id = _best_city_id(cluster, winner)
        category_id = _best_category_id(cluster, winner)
        address = _best_address(cluster, winner)
        phone = _best_phone(cluster, winner)
        website = _best_website(cluster, winner)
        lat, lng = _best_coordinates(cluster, winner)

        if not name:
            raise ValueError("Resolved cluster missing canonical name")

        if not city_id:
            raise ValueError("Resolved cluster missing city_id")

        place = _find_existing_place(
            db,
            name=name,
            city_id=city_id,
            lat=lat,
            lng=lng,
            address=address,
        )

        now = _utcnow()

        if place:
            _update_place_if_better(
                place,
                name=name,
                address=address,
                category_id=category_id,
                phone=phone,
                website=website,
                lat=lat,
                lng=lng,
                normalized_confidence=normalized_confidence,
                now=now,
            )

        else:
            place_kwargs = {
                "name": name,
                "city_id": city_id,
                "category_id": category_id,
                "address": address,
                "lat": lat,
                "lng": lng,
                "phone": phone,
                "website": website,
            }

            if hasattr(Place, "status"):
                place_kwargs["status"] = DEFAULT_STATUS

            if hasattr(Place, "confidence_score"):
                place_kwargs["confidence_score"] = normalized_confidence

            if hasattr(Place, "created_at"):
                place_kwargs["created_at"] = now

            if hasattr(Place, "updated_at"):
                place_kwargs["updated_at"] = now

            place = Place(**place_kwargs)

            db.add(place)
            db.flush()

        for candidate in cluster:
            if hasattr(candidate, "resolved"):
                candidate.resolved = True
            if hasattr(candidate, "updated_at"):
                candidate.updated_at = now

        return place

    def resolve_clusters(
        self,
        *,
        db: Session,
        clusters: List[List[DiscoveryCandidate]],
    ) -> List[Place]:
        places: List[Place] = []

        for cluster in clusters:
            try:
                place = self.resolve_cluster(db=db, cluster=cluster)
                places.append(place)
            except Exception as exc:
                logger.debug("resolve_cluster_failed error=%s", exc)

        return places