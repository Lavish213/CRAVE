from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.discovery_candidate import DiscoveryCandidate


UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def _normalize_name(name: str) -> str:
    return name.strip()


def _clamp_confidence(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0

    return max(0.0, min(1.0, v))


_MAX_CORROBORATION_KEYS = 50


def upsert_discovery_candidate_v2(
    *,
    db: Session,
    name: str,
    city_id: str,
    external_id: Optional[str] = None,
    source: Optional[str] = None,
    category_id: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    address: Optional[str] = None,
    phone: Optional[str] = None,
    website: Optional[str] = None,
    category_hint: Optional[str] = None,
    confidence_score: float = 0.0,
    raw_payload: Optional[dict] = None,
    contributor_key: Optional[str] = None,
) -> DiscoveryCandidate:
    """
    V2 Candidate Upsert (FULLY CONNECTED)

    Fixes:
    - Supports external_id (CRITICAL for multi-source ingest)
    - Stores source + raw_payload
    - Supports enrichment fields (address, phone, website)
    - Prevents duplicate candidates across sources
    - Still idempotent
    """

    if not name or not city_id:
        raise ValueError("name and city_id are required")

    name = _normalize_name(name)

    if not name:
        raise ValueError("invalid candidate name")

    lat = _safe_float(lat)
    lng = _safe_float(lng)
    confidence_score = _clamp_confidence(confidence_score)

    # ---------------------------------------------------
    # PRIMARY MATCH: external_id (BEST)
    # ---------------------------------------------------
    existing: Optional[DiscoveryCandidate] = None

    if external_id:
        existing = (
            db.query(DiscoveryCandidate)
            .filter(DiscoveryCandidate.external_id == external_id)
            .one_or_none()
        )

    # ---------------------------------------------------
    # FALLBACK MATCH: name + city
    # ---------------------------------------------------
    if not existing:
        existing = (
            db.query(DiscoveryCandidate)
            .filter(
                DiscoveryCandidate.city_id == city_id,
                func.lower(DiscoveryCandidate.name) == name.lower(),
            )
            .one_or_none()
        )

    # ---------------------------------------------------
    # UPDATE EXISTING
    # ---------------------------------------------------
    if existing:

        if category_id and not existing.category_id:
            existing.category_id = category_id

        if lat is not None:
            existing.lat = lat

        if lng is not None:
            existing.lng = lng

        if address and not existing.address:
            existing.address = address

        if phone and not existing.phone:
            existing.phone = phone

        if website and not existing.website:
            existing.website = website

        if category_hint and not existing.category_hint:
            existing.category_hint = category_hint

        if external_id and not existing.external_id:
            existing.external_id = external_id

        if source and not existing.source:
            existing.source = source

        if raw_payload and not existing.raw_payload:
            existing.raw_payload = raw_payload

        # contributor_key identifies "who/what independently vouched for
        # this place" (e.g. "user_gps:<user_id>", "user_share:<item_id>").
        # Automated/authoritative sources (OSM, Google Places, health dept)
        # never pass one — those keep the old max() merge, since a re-scan
        # by the same source isn't new evidence. But for user-corroboration
        # signals, max() is the bug: GPS (0.35), share (0.3), hitlist
        # suggestion (0.4), and hitlist save (0.45) can never sum past the
        # 0.72 promotion threshold under max() no matter how many distinct
        # people corroborate the same spot. A genuinely new contributor
        # accumulates instead; the same contributor re-submitting doesn't
        # let them single-handedly inflate confidence.
        if contributor_key:
            existing_keys = list(existing.corroboration_keys or [])
            if contributor_key not in existing_keys:
                existing_keys.append(contributor_key)
                existing.corroboration_keys = existing_keys[-_MAX_CORROBORATION_KEYS:]
                existing.confidence_score = _clamp_confidence(
                    existing.confidence_score + confidence_score
                )
            elif confidence_score > existing.confidence_score:
                existing.confidence_score = confidence_score
        elif confidence_score > existing.confidence_score:
            existing.confidence_score = confidence_score

        existing.updated_at = _utcnow()

        return existing

    # ---------------------------------------------------
    # CREATE NEW
    # ---------------------------------------------------
    candidate = DiscoveryCandidate(
        external_id=external_id,
        source=source,
        name=name,
        city_id=city_id,
        category_id=category_id,
        lat=lat,
        lng=lng,
        address=address,
        phone=phone,
        website=website,
        category_hint=category_hint,
        confidence_score=confidence_score,
        raw_payload=raw_payload,
        corroboration_keys=[contributor_key] if contributor_key else None,
        status="candidate",
        resolved=False,
        blocked=False,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )

    db.add(candidate)
    db.flush()

    return candidate