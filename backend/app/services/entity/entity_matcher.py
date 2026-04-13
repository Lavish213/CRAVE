from __future__ import annotations

import logging
from typing import Dict, Optional

from app.services.entity.dedupe_rules import (
    names_match,
    addresses_match,
)


logger = logging.getLogger(__name__)


# ~110 meters
SPATIAL_THRESHOLD = 0.001


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    try:
        v = str(value).strip().lower()
        return v if v else None
    except Exception:
        return None


def _extract_domain(url: Optional[str]) -> Optional[str]:
    """
    Normalize website → domain only
    """
    if not url:
        return None

    try:
        url = str(url).lower().strip()

        url = url.replace("https://", "")
        url = url.replace("http://", "")
        url = url.replace("www.", "")

        return url.split("/")[0]

    except Exception:
        return None


def _get_lat(candidate: Dict) -> Optional[float]:
    return _safe_float(candidate.get("lat"))


def _get_lng(candidate: Dict) -> Optional[float]:
    return _safe_float(candidate.get("lng") or candidate.get("lon"))


def _get_name(candidate: Dict) -> Optional[str]:
    return _normalize_text(
        candidate.get("normalized_name") or candidate.get("name")
    )


def _get_address(candidate: Dict) -> Optional[str]:
    return _normalize_text(
        candidate.get("normalized_address") or candidate.get("address")
    )


# ---------------------------------------------------------
# MATCH COMPONENTS
# ---------------------------------------------------------

def _names_match(a: Dict, b: Dict) -> bool:
    name_a = _get_name(a)
    name_b = _get_name(b)

    if not name_a or not name_b:
        return False

    try:
        return names_match(name_a, name_b)
    except Exception as exc:
        logger.debug("name_match_failed error=%s", exc)
        return False


def _addresses_match(a: Dict, b: Dict) -> bool:
    addr_a = _get_address(a)
    addr_b = _get_address(b)

    if not addr_a or not addr_b:
        return False

    try:
        return addresses_match(addr_a, addr_b)
    except Exception as exc:
        logger.debug("address_match_failed error=%s", exc)
        return False


def _spatial_match(a: Dict, b: Dict) -> bool:
    lat_a = _get_lat(a)
    lng_a = _get_lng(a)

    lat_b = _get_lat(b)
    lng_b = _get_lng(b)

    if lat_a is None or lng_a is None or lat_b is None or lng_b is None:
        return False

    try:
        return (
            abs(lat_a - lat_b) < SPATIAL_THRESHOLD
            and abs(lng_a - lng_b) < SPATIAL_THRESHOLD
        )
    except Exception:
        return False


def _website_match(a: Dict, b: Dict) -> bool:
    """
    Strong signal: domain match
    """

    wa = _extract_domain(a.get("website"))
    wb = _extract_domain(b.get("website"))

    if not wa or not wb:
        return False

    return wa == wb


# ---------------------------------------------------------
# MAIN MATCHER
# ---------------------------------------------------------

def entity_match(a: Dict, b: Dict) -> bool:
    """
    Production-grade entity matcher

    Logic:
    1. Name match is REQUIRED
    2. Strong signals:
        - address match
        - website match
    3. Spatial fallback (only if no strong signals)
    """

    try:

        # ---------------------------
        # HARD GATE
        # ---------------------------
        if not _names_match(a, b):
            return False

        # ---------------------------
        # STRONG SIGNALS
        # ---------------------------
        if _addresses_match(a, b):
            logger.debug("entity_match=address_match")
            return True

        if _website_match(a, b):
            logger.debug("entity_match=website_match")
            return True

        # ---------------------------
        # FALLBACK (SAFE)
        # ---------------------------
        if _spatial_match(a, b):
            logger.debug("entity_match=spatial_match")
            return True

    except Exception as exc:
        logger.debug("entity_match_failed error=%s", exc)

    return False