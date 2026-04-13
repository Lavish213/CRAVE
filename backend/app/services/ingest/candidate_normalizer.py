from __future__ import annotations

import logging
import re
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# -----------------------------------------------------
# ENTRYPOINT
# -----------------------------------------------------

def normalize_candidate(candidate: Dict) -> Optional[Dict]:
    """
    Normalize raw ingestion candidate into stable structure
    used across matching + writing pipeline.

    Guarantees:
    • clean + normalized name
    • normalized address
    • safe float parsing
    • normalized phone
    • normalized website + extracted domain
    • consistent output shape across all sources
    """

    try:
        name = _clean_string(candidate.get("name"))
        if not name:
            return None

        normalized_name = _normalize_name(name)

        address = _clean_string(candidate.get("address"))
        normalized_address = _normalize_address(address)

        lat = _safe_float(candidate.get("lat"))
        lng = _safe_float(candidate.get("lng") or candidate.get("lon"))

        phone = _clean_string(candidate.get("phone"))
        normalized_phone = _normalize_phone(phone)

        website = _normalize_url(candidate.get("website"))
        website_domain = _extract_domain(website)

        normalized = {
            # -------------------------------
            # IDENTITY
            # -------------------------------
            "external_id": _clean_string(candidate.get("external_id")),
            "source": _clean_string(candidate.get("source")),

            # -------------------------------
            # CORE
            # -------------------------------
            "name": name,
            "normalized_name": normalized_name,

            "address": address,
            "normalized_address": normalized_address,

            "city_id": _clean_string(candidate.get("city_id")),

            # -------------------------------
            # GEO
            # -------------------------------
            "lat": lat,
            "lng": lng,

            # -------------------------------
            # CONTACT
            # -------------------------------
            "phone": phone,
            "normalized_phone": normalized_phone,

            "website": website,
            "website_domain": website_domain,

            # -------------------------------
            # CLASSIFICATION
            # -------------------------------
            "category_hint": _clean_string(candidate.get("category_hint")),

            # -------------------------------
            # SCORING
            # -------------------------------
            "confidence": _safe_float(candidate.get("confidence")) or 0.0,

            # -------------------------------
            # RAW
            # -------------------------------
            "raw_payload": candidate.get("raw_payload"),
        }

        return normalized

    except Exception as e:
        logger.debug("candidate_normalize_failed error=%s", e)
        return None


# -----------------------------------------------------
# NORMALIZATION HELPERS
# -----------------------------------------------------

def _normalize_name(name: str) -> str:
    name = name.lower()

    name = name.replace("&", " and ")

    name = re.sub(r"[^\w\s]", " ", name)

    name = re.sub(r"\b(llc|inc|ltd|co|company)\b", "", name)

    name = re.sub(r"\s+", " ", name).strip()

    return name


def _normalize_address(address: Optional[str]) -> Optional[str]:
    if not address:
        return None

    address = address.lower()

    address = address.replace("street", "st")
    address = address.replace("avenue", "ave")
    address = address.replace("road", "rd")

    address = re.sub(r"[^\w\s]", " ", address)

    address = re.sub(r"\s+", " ", address).strip()

    return address


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    return digits if digits else None


def _normalize_url(url) -> Optional[str]:
    if not url:
        return None

    try:
        url = str(url).strip().lower()

        if not url.startswith("http"):
            url = f"https://{url}"

        return url

    except Exception:
        return None


def _extract_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    try:
        parsed = urlparse(url)
        domain = parsed.netloc

        if domain.startswith("www."):
            domain = domain[4:]

        return domain or None

    except Exception:
        return None


# -----------------------------------------------------
# BASIC HELPERS
# -----------------------------------------------------

def _clean_string(value) -> Optional[str]:
    if not value:
        return None

    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None