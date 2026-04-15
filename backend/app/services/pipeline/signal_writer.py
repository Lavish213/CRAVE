from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models.place_signal import PlaceSignal
from app.services.pipeline.place_resolver import ResolvedCandidate

logger = logging.getLogger(__name__)

# Valid signal types (must match intake API)
VALID_SIGNAL_TYPES = frozenset({
    "creator", "award", "blog", "save", "review", "trending", "mention"
})

# Valid providers
VALID_PROVIDERS = frozenset({
    "google", "yelp", "tiktok", "instagram", "youtube",
    "michelin", "eater", "infatuation", "internal", "grubhub", "generic"
})

# Platform → provider mapping
PLATFORM_TO_PROVIDER = {
    "tiktok": "tiktok",
    "instagram": "instagram",
    "youtube": "youtube",
    "grubhub": "grubhub",
    "google_maps": "google",
    "yelp": "yelp",
    "generic": "generic",
    "unknown": "generic",
}

# Signal type per platform
PLATFORM_TO_SIGNAL_TYPE = {
    "tiktok": "creator",
    "instagram": "creator",
    "youtube": "creator",
    "grubhub": "save",
    "google_maps": "review",
    "yelp": "review",
    "generic": "mention",
    "unknown": "mention",
}


@dataclass
class WriteResult:
    place_id: str
    signal_id: Optional[int]
    duplicate: bool
    skipped: bool
    reason: Optional[str] = None


def write_signal(
    db: Session,
    resolved: ResolvedCandidate,
    *,
    signal_type: Optional[str] = None,
    provider: Optional[str] = None,
    value: float = 0.5,
    external_event_id: Optional[str] = None,
) -> Optional[WriteResult]:
    """
    Write a PlaceSignal for a resolved candidate.
    Returns None if candidate is unresolved.
    Is idempotent — duplicate signals are silently ignored.
    """
    if not resolved.place_id:
        return None

    c = resolved.candidate

    # Derive signal_type + provider from platform if not explicit
    _signal_type = signal_type or PLATFORM_TO_SIGNAL_TYPE.get(c.source_platform, "mention")
    _provider = provider or PLATFORM_TO_PROVIDER.get(c.source_platform, "generic")

    # Validate
    if _signal_type not in VALID_SIGNAL_TYPES:
        logger.warning("signal_write_invalid_type type=%s", _signal_type)
        return WriteResult(place_id=resolved.place_id, signal_id=None, duplicate=False, skipped=True, reason="invalid_signal_type")

    if _provider not in VALID_PROVIDERS:
        _provider = "generic"

    # Clamp value
    value = max(0.0, min(1.0, float(value)))

    # Build external_event_id for dedup
    _ext_id = external_event_id or c.source_url or c.external_id or f"{c.source_platform}:{c.name}"

    signal = PlaceSignal(
        place_id=resolved.place_id,
        provider=_provider,
        signal_type=_signal_type,
        value=value,
        raw_value=str(c.confidence),
        external_event_id=_ext_id,
    )

    try:
        db.add(signal)
        db.flush()
        logger.debug(
            "signal_written place_id=%s type=%s provider=%s value=%.2f",
            resolved.place_id, _signal_type, _provider, value,
        )
        return WriteResult(
            place_id=resolved.place_id,
            signal_id=signal.id,
            duplicate=False,
            skipped=False,
        )

    except IntegrityError:
        db.rollback()
        logger.debug(
            "signal_duplicate place_id=%s type=%s ext_id=%s",
            resolved.place_id, _signal_type, _ext_id,
        )
        return WriteResult(
            place_id=resolved.place_id,
            signal_id=None,
            duplicate=True,
            skipped=False,
        )
