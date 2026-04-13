from __future__ import annotations

import json
import logging
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from config.health_datasets import get_health_dataset
from ingest.filters.health_row_sanitizer import sanitize_health_rows
from ingest.sources.socrata_fetch import fetch_socrata_dataset
from scripts.ingest.promote_health_places import promote_health_places
from scripts.run_arcgis_ingest import run_arcgis_ingest


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

DEFAULT_SOURCE = "health"
DEFAULT_JSON_INDENT = 2
MIN_PHONE_DIGITS = 7
DEFAULT_CATEGORY_HINT = "restaurant"
MAX_ROWS_PROTECTION = 2_000_000

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
}

INACTIVE_STATUS_TOKENS = {
    "inactive",
    "closed",
    "revoked",
    "expired",
    "suspended",
    "cancelled",
    "canceled",
    "out of business",
}

SUPPORTED_DATASET_TYPES = {
    "socrata",
    "arcgis",
}


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _raw_dir() -> Path:
    path = _project_root() / "data" / "raw" / "health"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

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


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    value = _clean(value)

    if not value:
        return None

    digits = "".join(ch for ch in value if ch.isdigit())

    if len(digits) < MIN_PHONE_DIGITS:
        return None

    return digits


def _normalize_website(value: Optional[str]) -> Optional[str]:
    value = _clean(value)

    if not value:
        return None

    if not value.startswith(("http://", "https://")):
        value = "https://" + value

    return value


def _canonical_city_slug(city_slug: str) -> str:
    return city_slug.strip().lower()


def _normalize_name(value: Optional[str]) -> Optional[str]:
    name = _clean(value)

    if not name:
        return None

    upper = name.upper()

    if upper in PLACEHOLDER_NAMES:
        return None

    name = re.sub(r"\s+", " ", name).strip()

    return name or None


def _build_address(row: Dict[str, Any], address_field: Optional[str]) -> Optional[str]:
    if address_field:
        return _clean(row.get(address_field))

    return None


def _round_coord(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None

    try:
        return round(float(value), 6)
    except Exception:
        return None


def _normalize_where(value: Any) -> Optional[str]:
    cleaned = _clean(value)

    if not cleaned:
        return None

    if cleaned.lower() == "none":
        return None

    return cleaned


def _dataset_type(config: Any) -> str:
    dataset_type = _clean(getattr(config, "dataset_type", None))

    if not dataset_type:
        raise RuntimeError(
            f"Missing dataset_type for city '{getattr(config, 'city_slug', 'unknown')}'"
        )

    dataset_type = dataset_type.lower()

    if dataset_type not in SUPPORTED_DATASET_TYPES:
        raise RuntimeError(
            f"Unsupported dataset_type '{dataset_type}' for city "
            f"'{getattr(config, 'city_slug', 'unknown')}'"
        )

    return dataset_type


# ---------------------------------------------------------
# External ID Builder
# ---------------------------------------------------------

def _slugify_for_id(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def _build_external_id(
    *,
    source: str,
    city_slug: str,
    dataset_id: str,
    permit_id: Optional[str],
    facility_id: Optional[str],
    row_id: Optional[str],
    name: Optional[str],
    address: Optional[str],
) -> Optional[str]:

    if permit_id:
        return f"{source}:{city_slug}:permit:{permit_id}"

    if facility_id:
        return f"{source}:{city_slug}:facility:{facility_id}"

    if row_id:
        return f"{source}:{city_slug}:{dataset_id}:{row_id}"

    if name and address:
        synthetic_name = _slugify_for_id(name)
        synthetic_address = _slugify_for_id(address)
        return f"{source}:{city_slug}:synthetic:{synthetic_name}:{synthetic_address}"

    return None


# ---------------------------------------------------------
# Health Dataset Filters
# ---------------------------------------------------------

def _row_is_active(row: Dict[str, Any], config: Any) -> bool:

    status_field = getattr(config, "status_field", None)
    status_active_values = getattr(config, "status_active_values", None)

    if not status_field:
        return True

    status_value = _clean(row.get(status_field))

    if not status_value:
        return True

    if status_active_values:
        normalized_allowed = {
            str(v).strip().lower()
            for v in status_active_values
            if str(v).strip()
        }

        return status_value.lower() in normalized_allowed

    return status_value.lower() not in INACTIVE_STATUS_TOKENS


def _row_category_hint(row: Dict[str, Any], config: Any) -> Optional[str]:

    configured = _clean(getattr(config, "category_hint", None))

    if configured:
        return configured

    for field_name in (
        getattr(config, "category_field", None),
        getattr(config, "permit_type_field", None),
        getattr(config, "facility_type_field", None),
        "facility_type",
        "FACILITY_TYPE",
        "category",
        "CATEGORY",
    ):

        if field_name:

            value = _clean(row.get(field_name))

            if value:
                return value

    return DEFAULT_CATEGORY_HINT


def _row_confidence(config: Any, has_coords: bool) -> float:

    base = getattr(config, "confidence", 0.80)

    try:
        confidence = float(base)
    except Exception:
        confidence = 0.80

    if not has_coords:
        confidence -= 0.08

    return max(0.0, min(1.0, confidence))


def _row_has_usable_coords(lat: Optional[float], lng: Optional[float]) -> bool:

    if lat is None or lng is None:
        return False

    if not (-90 <= lat <= 90):
        return False

    if not (-180 <= lng <= 180):
        return False

    if lat == 0.0 and lng == 0.0:
        return False

    return True


# ---------------------------------------------------------
# Normalization
# ---------------------------------------------------------

def _normalize_rows(
    *,
    rows: List[Dict[str, Any]],
    config: Any,
) -> List[Dict[str, Any]]:

    normalized: List[Dict[str, Any]] = []

    seen_external_ids: Set[str] = set()

    skipped_inactive = 0
    skipped_invalid = 0
    skipped_duplicates = 0
    skipped_missing_identity = 0
    skipped_bad_coords = 0

    dataset_id = _clean(getattr(config, "dataset_id", None)) or "dataset"

    for row in rows:

        try:

            if not _row_is_active(row, config):
                skipped_inactive += 1
                continue

            name_field = getattr(config, "name_field", None)
            name = _normalize_name(row.get(name_field) if name_field else None)

            if not name:
                skipped_missing_identity += 1
                continue

            lat = (
                _safe_float(row.get(config.lat_field))
                if getattr(config, "lat_field", None)
                else None
            )

            lng = (
                _safe_float(row.get(config.lng_field))
                if getattr(config, "lng_field", None)
                else None
            )

            has_coords = _row_has_usable_coords(lat, lng)

            if lat is not None or lng is not None:
                if not has_coords:
                    skipped_bad_coords += 1
                    lat = None
                    lng = None

            address = _build_address(row, getattr(config, "address_field", None))

            if not has_coords and not address:
                skipped_invalid += 1
                continue

            phone = _normalize_phone(
                row.get(config.phone_field)
                if getattr(config, "phone_field", None)
                else None
            )

            website = _normalize_website(
                row.get(config.website_field)
                if getattr(config, "website_field", None)
                else None
            )

            permit_id = (
                _clean(row.get(config.permit_id_field))
                if getattr(config, "permit_id_field", None)
                else None
            )

            facility_id = (
                _clean(row.get(config.facility_id_field))
                if getattr(config, "facility_id_field", None)
                else None
            )

            row_id = _clean(row.get(":id"))

            external_id = _build_external_id(
                source=DEFAULT_SOURCE,
                city_slug=getattr(config, "city_slug", "unknown"),
                dataset_id=dataset_id,
                permit_id=permit_id,
                facility_id=facility_id,
                row_id=row_id,
                name=name,
                address=address,
            )

            if not external_id:
                skipped_missing_identity += 1
                continue

            if external_id in seen_external_ids:
                skipped_duplicates += 1
                continue

            seen_external_ids.add(external_id)

            record = {
                "external_id": external_id,
                "name": name,
                "address": address,
                "lat": _round_coord(lat),
                "lng": _round_coord(lng),
                "phone": phone,
                "website": website,
                "category_hint": _row_category_hint(row, config),
                "source": DEFAULT_SOURCE,
                "confidence": _row_confidence(config, has_coords),
                "raw_payload": row,
            }

            normalized.append(record)

        except Exception as exc:

            skipped_invalid += 1

            logger.debug(
                "health_normalization_failed city=%s error=%s row=%s",
                getattr(config, "city_slug", "unknown"),
                exc,
                row,
            )

    logger.info(
        "health_normalization_summary city=%s kept=%s skipped_inactive=%s skipped_invalid=%s skipped_duplicates=%s skipped_missing_identity=%s skipped_bad_coords=%s",
        getattr(config, "city_slug", "unknown"),
        len(normalized),
        skipped_inactive,
        skipped_invalid,
        skipped_duplicates,
        skipped_missing_identity,
        skipped_bad_coords,
    )

    return normalized


# ---------------------------------------------------------
# Checkpoint Writer
# ---------------------------------------------------------

def _write_checkpoint(city_slug: str, rows: List[Dict[str, Any]]) -> Path:

    final_path = _raw_dir() / f"{city_slug}_health_places.json"

    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        dir=_raw_dir(),
        encoding="utf-8",
    ) as tmp:

        json.dump(rows, tmp, ensure_ascii=False, indent=DEFAULT_JSON_INDENT)

        tmp.flush()

        temp_path = Path(tmp.name)

    temp_path.replace(final_path)

    return final_path


# ---------------------------------------------------------
# Socrata Runner
# ---------------------------------------------------------

def _run_socrata_dataset(city_slug: str, config: Any) -> None:

    domain = _clean(getattr(config, "domain", None))
    dataset_id = _clean(getattr(config, "dataset_id", None))

    if not domain or not dataset_id:
        raise RuntimeError(f"Invalid Socrata dataset config for {city_slug}")

    start = time.time()

    rows = fetch_socrata_dataset(
        domain=domain,
        dataset_id=dataset_id,
        app_token=getattr(config, "app_token", None),
        select=getattr(config, "select", None),
        where=_normalize_where(getattr(config, "where", None)),
        limit=getattr(config, "page_limit", 50000),
        max_pages=getattr(config, "max_pages", None),
        use_cache=getattr(config, "use_cache", True),
        force_refresh=getattr(config, "force_refresh", False),
    )

    elapsed = round(time.time() - start, 2)

    logger.info(
        "health_rows_fetched city=%s count=%s seconds=%s",
        city_slug,
        len(rows),
        elapsed,
    )

    if len(rows) > MAX_ROWS_PROTECTION:
        raise RuntimeError(
            f"Socrata dataset too large ({len(rows)} rows) limit={MAX_ROWS_PROTECTION}"
        )

    if not rows:
        logger.warning("health_rows_empty city=%s", city_slug)
        return

    rows = sanitize_health_rows(
        rows=rows,
        config=config,
    )

    logger.info("health_rows_sanitized city=%s count=%s", city_slug, len(rows))

    if not rows:
        logger.warning("health_rows_sanitized_empty city=%s", city_slug)
        return

    normalized = _normalize_rows(rows=rows, config=config)

    logger.info("health_rows_normalized city=%s count=%s", city_slug, len(normalized))

    if not normalized:
        logger.warning("health_rows_normalized_empty city=%s", city_slug)
        return

    checkpoint = _write_checkpoint(city_slug, normalized)

    logger.info("health_checkpoint_written city=%s path=%s", city_slug, checkpoint)

    try:
        promote_health_places(city_slug)
        logger.info("health_promotion_complete city=%s", city_slug)

    except Exception as exc:
        logger.exception(
            "health_promotion_failed city=%s error=%s",
            city_slug,
            exc,
        )
        raise


# ---------------------------------------------------------
# Unified Runner
# ---------------------------------------------------------

def run_health_ingest(city_slug: str) -> None:

    city_slug = _canonical_city_slug(city_slug)

    logger.info("health_ingest_start city=%s", city_slug)

    config = get_health_dataset(city_slug)

    dataset_type = _dataset_type(config)

    logger.info(
        "health_ingest_dataset_type city=%s dataset_type=%s",
        city_slug,
        dataset_type,
    )

    if dataset_type == "socrata":
        _run_socrata_dataset(city_slug, config)
        return

    if dataset_type == "arcgis":
        run_arcgis_ingest(city_slug)
        return

    raise RuntimeError(
        f"Unsupported dataset_type '{dataset_type}' for city '{city_slug}'"
    )


# ---------------------------------------------------------
# Backwards Compatible Socrata Entry Point
# ---------------------------------------------------------

def run_socrata_ingest(city_slug: str) -> None:

    city_slug = _canonical_city_slug(city_slug)

    config = get_health_dataset(city_slug)

    dataset_type = _dataset_type(config)

    if dataset_type != "socrata":
        logger.warning(
            "run_socrata_ingest_auto_reroute city=%s dataset_type=%s",
            city_slug,
            dataset_type,
        )
        run_health_ingest(city_slug)
        return

    _run_socrata_dataset(city_slug, config)


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    if len(sys.argv) < 2:

        print("Usage:")
        print("python scripts/run_socrata_ingest.py <city_slug>")

        sys.exit(1)

    city_slug = sys.argv[1].lower().strip()

    run_health_ingest(city_slug)


if __name__ == "__main__":
    main()