from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

PLACEHOLDER_NAMES = {
    "N/A",
    "NA",
    "NONE",
    "UNKNOWN",
    "TBD",
    "NO NAME",
    "NULL",
    "TEST",
    "TEST RECORD",
    "DUPLICATE",
    "DUPLICATE ENTRY",
    "TEMP",
    "TEMP RECORD",
    "PENDING",
}

PLACEHOLDER_ADDRESSES = {
    "N/A",
    "NA",
    "NONE",
    "UNKNOWN",
    "NO ADDRESS",
    "NULL",
    "TBD",
}

INACTIVE_STATUS_TOKENS = {
    "inactive",
    "closed",
    "revoked",
    "expired",
    "suspended",
    "cancelled",
    "canceled",
    "inactive permit",
    "closed facility",
    "out of business",
}

NON_RESTAURANT_KEYWORDS = {
    "school",
    "hospital",
    "warehouse",
    "food bank",
    "church",
    "office",
    "admin",
    "administration",
    "department",
    "county office",
    "health office",
    "government",
    "district office",
    "storage",
    "distribution center",
    "commissary only",
}

EXCLUDED_NAME_KEYWORDS = {
    "test",
    "duplicate",
    "temporary",
    "temp record",
    "unknown",
    "no name",
    "admin office",
    "inspection office",
    "county health",
}

EXCLUDED_FACILITY_TYPE_KEYWORDS = {
    "school",
    "hospital",
    "food bank",
    "warehouse",
    "church",
    "office",
    "government",
    "mobile support",
    "commissary",
    "temporary event",
    "temporary food",
}

MIN_NAME_LENGTH = 2

US_LAT_RANGE = (20.0, 60.0)
US_LNG_RANGE = (-130.0, -60.0)


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None

    value = str(value).strip()
    return value or None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except Exception:
        return None


def _normalize_text(value: Optional[str]) -> Optional[str]:
    value = _clean(value)
    if not value:
        return None

    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _normalize_name(value: Optional[str]) -> Optional[str]:
    value = _normalize_text(value)
    if not value:
        return None

    upper = value.upper()
    if upper in PLACEHOLDER_NAMES:
        return None

    if len(value) < MIN_NAME_LENGTH:
        return None

    return value


def _normalize_address(value: Optional[str]) -> Optional[str]:
    value = _normalize_text(value)
    if not value:
        return None

    if value.upper() in PLACEHOLDER_ADDRESSES:
        return None

    return value


def _contains_any(text: Optional[str], keywords: Set[str]) -> bool:
    if not text:
        return False

    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _coords_valid(lat: Optional[float], lng: Optional[float]) -> bool:
    if lat is None or lng is None:
        return False

    if lat == 0.0 and lng == 0.0:
        return False

    if not (-90.0 <= lat <= 90.0):
        return False

    if not (-180.0 <= lng <= 180.0):
        return False

    if not (US_LAT_RANGE[0] <= lat <= US_LAT_RANGE[1]):
        return False

    if not (US_LNG_RANGE[0] <= lng <= US_LNG_RANGE[1]):
        return False

    return True


def _row_status(row: Dict[str, Any], config: Any) -> Optional[str]:
    status_field = getattr(config, "status_field", None)
    if not status_field:
        return None

    status = _clean(row.get(status_field))
    if not status:
        return None

    return status.lower()


def _row_category_tokens(row: Dict[str, Any], config: Any) -> List[str]:
    values: List[str] = []

    for field_name in (
        getattr(config, "category_field", None),
        getattr(config, "facility_type_field", None),
        getattr(config, "permit_type_field", None),
    ):
        if field_name:
            value = _clean(row.get(field_name))
            if value:
                values.append(value.lower())

    configured_hint = _clean(getattr(config, "category_hint", None))
    if configured_hint:
        values.append(configured_hint.lower())

    return values


def _build_identity_key(
    *,
    name: Optional[str],
    address: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
) -> Optional[Tuple[str, str, Optional[float], Optional[float]]]:
    if not name:
        return None

    key_name = name.lower()
    key_address = (address or "").lower()
    key_lat = round(lat, 5) if lat is not None else None
    key_lng = round(lng, 5) if lng is not None else None

    return (key_name, key_address, key_lat, key_lng)


def sanitize_health_rows(
    *,
    rows: List[Dict[str, Any]],
    config: Any,
) -> List[Dict[str, Any]]:
    """
    Fetch-level sanitizer for raw health rows.

    Purpose:
    - remove obvious junk before normalization
    - reduce DB pollution
    - keep normalization focused on canonical mapping

    This should stay source-agnostic enough to work for both
    Socrata and ArcGIS-backed health datasets.
    """

    kept: List[Dict[str, Any]] = []
    seen_identity_keys: Set[Tuple[str, str, Optional[float], Optional[float]]] = set()

    skipped_status = 0
    skipped_name = 0
    skipped_address = 0
    skipped_coords = 0
    skipped_non_restaurant = 0
    skipped_duplicate = 0
    skipped_other = 0

    name_field = getattr(config, "name_field", None)
    address_field = getattr(config, "address_field", None)
    lat_field = getattr(config, "lat_field", None)
    lng_field = getattr(config, "lng_field", None)

    allow_address_only = bool(getattr(config, "allow_address_only", True))
    status_active_values = getattr(config, "status_active_values", None)

    normalized_allowed_statuses = None
    if status_active_values:
        normalized_allowed_statuses = {
            str(value).strip().lower()
            for value in status_active_values
            if str(value).strip()
        }

    for row in rows:
        try:
            name = _normalize_name(row.get(name_field) if name_field else None)
            if not name:
                skipped_name += 1
                continue

            if _contains_any(name, EXCLUDED_NAME_KEYWORDS):
                skipped_name += 1
                continue

            address = _normalize_address(row.get(address_field) if address_field else None)

            lat = _safe_float(row.get(lat_field)) if lat_field else None
            lng = _safe_float(row.get(lng_field)) if lng_field else None

            has_valid_coords = _coords_valid(lat, lng)

            if not has_valid_coords:
                lat = None
                lng = None

            if not address and not allow_address_only and not has_valid_coords:
                skipped_address += 1
                continue

            if not address and not has_valid_coords:
                skipped_address += 1
                continue

            status = _row_status(row, config)
            if status:
                if normalized_allowed_statuses is not None:
                    if status not in normalized_allowed_statuses:
                        skipped_status += 1
                        continue
                elif _contains_any(status, INACTIVE_STATUS_TOKENS):
                    skipped_status += 1
                    continue

            category_tokens = _row_category_tokens(row, config)
            combined_category_text = " | ".join(category_tokens) if category_tokens else None

            if _contains_any(name, NON_RESTAURANT_KEYWORDS):
                skipped_non_restaurant += 1
                continue

            if _contains_any(address, {"po box", "p.o. box"}):
                skipped_address += 1
                continue

            if _contains_any(combined_category_text, EXCLUDED_FACILITY_TYPE_KEYWORDS):
                skipped_non_restaurant += 1
                continue

            identity_key = _build_identity_key(
                name=name,
                address=address,
                lat=lat,
                lng=lng,
            )

            if identity_key and identity_key in seen_identity_keys:
                skipped_duplicate += 1
                continue

            if identity_key:
                seen_identity_keys.add(identity_key)

            sanitized_row = dict(row)

            if name_field:
                sanitized_row[name_field] = name

            if address_field and address:
                sanitized_row[address_field] = address

            if lat_field:
                sanitized_row[lat_field] = lat

            if lng_field:
                sanitized_row[lng_field] = lng

            kept.append(sanitized_row)

        except Exception as exc:
            skipped_other += 1
            logger.debug(
                "health_row_sanitizer_failed city=%s error=%s row=%s",
                getattr(config, "city_slug", "unknown"),
                exc,
                row,
            )

    logger.info(
        "health_row_sanitizer_summary city=%s input=%s kept=%s skipped_status=%s skipped_name=%s skipped_address=%s skipped_coords=%s skipped_non_restaurant=%s skipped_duplicate=%s skipped_other=%s",
        getattr(config, "city_slug", "unknown"),
        len(rows),
        len(kept),
        skipped_status,
        skipped_name,
        skipped_address,
        skipped_coords,
        skipped_non_restaurant,
        skipped_duplicate,
        skipped_other,
    )

    return kept