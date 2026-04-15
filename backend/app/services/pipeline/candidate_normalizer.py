from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum confidence to pass through normalization
MIN_CONFIDENCE = 0.30

# Place name validation
MIN_NAME_LEN = 3
MAX_NAME_LEN = 120

# Reject these exact/partial strings as place names
_JUNK_NAMES = frozenset({
    "tiktok", "instagram", "youtube", "reels", "shorts", "video",
    "follow", "subscribe", "link in bio", "dm", "swipe", "tag",
    "restaurant", "food", "place", "location", "spot", "here",
})


@dataclass
class NormalizedCandidate:
    name: str
    lat: Optional[float]
    lng: Optional[float]
    city_hint: Optional[str]
    source_platform: str  # tiktok|instagram|youtube|google_maps|grubhub|yelp|generic|unknown
    source_url: Optional[str]
    confidence: float  # 0.0–1.0
    raw: dict = field(default_factory=dict)
    external_id: Optional[str] = None  # stable dedup key from source


def normalize(raw: dict) -> Optional[NormalizedCandidate]:
    """
    Convert raw scraper/legacy output into a NormalizedCandidate.
    Returns None if the candidate should be rejected.

    Input shape (flexible — handles multiple legacy formats):
    {
        "name": str,                    # required
        "lat": float | None,
        "lng": float | None,
        "city": str | None,
        "city_hint": str | None,
        "source_platform": str | None,
        "source_url": str | None,
        "confidence": float | None,
        "external_url": str | None,     # OSM format alias for source_url
        "id": str | None,               # external dedup ID
    }
    """
    try:
        name = _extract_name(raw)
        if not name:
            return None

        lat = _extract_float(raw, "lat")
        lng = _extract_float(raw, "lng") or _extract_float(raw, "lon")

        city_hint = raw.get("city") or raw.get("city_hint") or raw.get("addr_city")
        source_platform = _normalize_platform(raw.get("source_platform", "unknown"))
        source_url = raw.get("source_url") or raw.get("external_url")
        if source_url:
            source_url = _clean_url(source_url)

        confidence = _compute_confidence(raw, name, lat, lng, source_url)
        if confidence < MIN_CONFIDENCE:
            logger.debug("candidate_rejected_low_confidence name=%s confidence=%.2f", name, confidence)
            return None

        external_id = str(raw.get("id", "")) or None

        return NormalizedCandidate(
            name=name,
            lat=lat,
            lng=lng,
            city_hint=city_hint,
            source_platform=source_platform,
            source_url=source_url,
            confidence=confidence,
            raw=raw,
            external_id=external_id,
        )

    except Exception as exc:
        logger.warning("candidate_normalize_failed error=%s raw=%s", exc, str(raw)[:200])
        return None


def normalize_batch(records: list[dict]) -> list[NormalizedCandidate]:
    """Normalize a list of raw records. Silently drops rejected ones."""
    results = []
    for r in records:
        c = normalize(r)
        if c:
            results.append(c)
    logger.info("candidate_normalize_batch input=%s accepted=%s", len(records), len(results))
    return results


# ---------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------

def _extract_name(raw: dict) -> Optional[str]:
    name = raw.get("name") or raw.get("place_name") or raw.get("place_name_hint")
    if not name:
        return None
    name = str(name).strip()
    # Length check
    if len(name) < MIN_NAME_LEN or len(name) > MAX_NAME_LEN:
        return None
    # Junk check
    lower = name.lower()
    if any(j in lower for j in _JUNK_NAMES):
        return None
    # Pure emoji/punctuation reject
    if re.fullmatch(r"[^\w\s]+", name):
        return None
    return name


def _extract_float(raw: dict, key: str) -> Optional[float]:
    val = raw.get(key)
    if val is None:
        return None
    try:
        f = float(val)
        return f if f != 0.0 else None
    except (TypeError, ValueError):
        return None


def _normalize_platform(platform: Optional[str]) -> str:
    if not platform:
        return "unknown"
    p = platform.lower().strip()
    known = {"tiktok", "instagram", "youtube", "google_maps", "grubhub", "yelp", "generic"}
    return p if p in known else "generic"


def _clean_url(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    # Strip tracking params
    url = re.sub(r"[?&](utm_[^&]+|fbclid=[^&]+|igshid=[^&]+|gclid=[^&]+)", "", url)
    url = url.rstrip("?&")
    if not url.startswith(("http://", "https://")):
        return None
    return url


def _compute_confidence(
    raw: dict,
    name: str,
    lat: Optional[float],
    lng: Optional[float],
    source_url: Optional[str],
) -> float:
    # Start from explicit confidence if provided
    base = float(raw.get("confidence", 0.0))
    if isinstance(raw.get("confidence"), str):
        base = {"high": 0.75, "medium": 0.50, "low": 0.25}.get(raw["confidence"], 0.0)

    # Build from signals if no explicit confidence
    if base == 0.0:
        base = 0.20  # name alone
        if lat and lng:
            base += 0.30
        if source_url:
            base += 0.15
        if raw.get("city") or raw.get("city_hint"):
            base += 0.10

    return min(1.0, base)
