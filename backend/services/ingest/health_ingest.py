from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from config.city_loader import load_all_cities, load_region_map
from config.health_datasets import (
    get_health_dataset,
    list_health_datasets,
)
from scripts.run_arcgis_ingest import run_arcgis_ingest
from scripts.run_socrata_ingest import run_socrata_ingest


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Result Model
# ---------------------------------------------------------

@dataclass
class HealthIngestResult:
    scope: str
    total: int
    succeeded: int
    failed: int
    skipped: int
    duration_seconds: float
    errors: Dict[str, str]


# ---------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------

def _normalize_slug(value: str) -> str:
    return str(value).strip().lower()


def _run_city(city_slug: str) -> None:
    city_slug = _normalize_slug(city_slug)

    config = get_health_dataset(city_slug)
    dataset_type = getattr(config, "dataset_type", None)

    if dataset_type == "arcgis":
        run_arcgis_ingest(city_slug)
        return

    if dataset_type == "socrata":
        run_socrata_ingest(city_slug)
        return

    raise RuntimeError(
        f"Unsupported dataset_type '{dataset_type}' for city '{city_slug}'"
    )


def _build_result(
    *,
    scope: str,
    total: int,
    succeeded: int,
    failed: int,
    skipped: int,
    start: float,
    errors: Dict[str, str],
) -> HealthIngestResult:
    return HealthIngestResult(
        scope=scope,
        total=total,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        duration_seconds=round(time.time() - start, 2),
        errors=errors,
    )


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []

    for value in values:
        slug = _normalize_slug(value)

        if not slug or slug in seen:
            continue

        seen.add(slug)
        result.append(slug)

    return result


# ---------------------------------------------------------
# Public API: Single City
# ---------------------------------------------------------

def run_health_city(city_slug: str) -> HealthIngestResult:
    city_slug = _normalize_slug(city_slug)

    logger.info("health_city_start city=%s", city_slug)

    start = time.time()
    errors: Dict[str, str] = {}

    try:
        _run_city(city_slug)

        result = _build_result(
            scope=f"city:{city_slug}",
            total=1,
            succeeded=1,
            failed=0,
            skipped=0,
            start=start,
            errors=errors,
        )

        logger.info(
            "health_city_complete city=%s succeeded=%s failed=%s seconds=%s",
            city_slug,
            result.succeeded,
            result.failed,
            result.duration_seconds,
        )

        return result

    except Exception as exc:
        errors[city_slug] = str(exc)

        logger.exception(
            "health_city_failed city=%s error=%s",
            city_slug,
            exc,
        )

        result = _build_result(
            scope=f"city:{city_slug}",
            total=1,
            succeeded=0,
            failed=1,
            skipped=0,
            start=start,
            errors=errors,
        )

        logger.info(
            "health_city_complete city=%s succeeded=%s failed=%s seconds=%s",
            city_slug,
            result.succeeded,
            result.failed,
            result.duration_seconds,
        )

        return result


# ---------------------------------------------------------
# Public API: Region
# ---------------------------------------------------------

def run_health_region(region_name: str) -> HealthIngestResult:
    region_name = _normalize_slug(region_name)

    logger.info("health_region_start region=%s", region_name)

    start = time.time()
    errors: Dict[str, str] = {}

    region_map = load_region_map()

    if region_name not in region_map:
        available = ", ".join(sorted(region_map.keys()))
        raise RuntimeError(
            f"Region '{region_name}' not found. Available: {available}"
        )

    region_cities = _dedupe_preserve_order(region_map[region_name])
    configured_cities = set(list_health_datasets())

    succeeded = 0
    failed = 0
    skipped = 0

    for city_slug in region_cities:
        if city_slug not in configured_cities:
            skipped += 1
            errors[city_slug] = "missing_health_dataset_config"

            logger.warning(
                "health_region_city_skipped city=%s reason=missing_health_dataset_config",
                city_slug,
            )
            continue

        try:
            logger.info("health_region_city_start city=%s", city_slug)

            _run_city(city_slug)

            succeeded += 1

            logger.info("health_region_city_complete city=%s", city_slug)

        except Exception as exc:
            failed += 1
            errors[city_slug] = str(exc)

            logger.exception(
                "health_region_city_failed city=%s error=%s",
                city_slug,
                exc,
            )

    result = _build_result(
        scope=f"region:{region_name}",
        total=len(region_cities),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        start=start,
        errors=errors,
    )

    logger.info(
        "health_region_complete region=%s total=%s succeeded=%s failed=%s skipped=%s seconds=%s",
        region_name,
        result.total,
        result.succeeded,
        result.failed,
        result.skipped,
        result.duration_seconds,
    )

    return result


# ---------------------------------------------------------
# Public API: All Configured Datasets
# ---------------------------------------------------------

def run_health_all_configured() -> HealthIngestResult:
    start = time.time()
    errors: Dict[str, str] = {}

    configured_cities = _dedupe_preserve_order(list_health_datasets())

    logger.info(
        "health_all_configured_start cities=%s",
        len(configured_cities),
    )

    succeeded = 0
    failed = 0

    for city_slug in configured_cities:
        try:
            logger.info("health_all_configured_city_start city=%s", city_slug)

            _run_city(city_slug)

            succeeded += 1

            logger.info("health_all_configured_city_complete city=%s", city_slug)

        except Exception as exc:
            failed += 1
            errors[city_slug] = str(exc)

            logger.exception(
                "health_all_configured_city_failed city=%s error=%s",
                city_slug,
                exc,
            )

    result = _build_result(
        scope="all_configured",
        total=len(configured_cities),
        succeeded=succeeded,
        failed=failed,
        skipped=0,
        start=start,
        errors=errors,
    )

    logger.info(
        "health_all_configured_complete total=%s succeeded=%s failed=%s seconds=%s",
        result.total,
        result.succeeded,
        result.failed,
        result.duration_seconds,
    )

    return result


# ---------------------------------------------------------
# Public API: All Cities In Region Files
# ---------------------------------------------------------

def run_health_all_regions() -> HealthIngestResult:
    start = time.time()
    errors: Dict[str, str] = {}

    region_map = load_region_map()
    all_region_cities = _dedupe_preserve_order(load_all_cities())
    configured_cities = set(list_health_datasets())

    logger.info(
        "health_all_regions_start regions=%s cities=%s",
        len(region_map),
        len(all_region_cities),
    )

    succeeded = 0
    failed = 0
    skipped = 0

    for city_slug in all_region_cities:
        if city_slug not in configured_cities:
            skipped += 1
            errors[city_slug] = "missing_health_dataset_config"

            logger.warning(
                "health_all_regions_city_skipped city=%s reason=missing_health_dataset_config",
                city_slug,
            )
            continue

        try:
            logger.info("health_all_regions_city_start city=%s", city_slug)

            _run_city(city_slug)

            succeeded += 1

            logger.info("health_all_regions_city_complete city=%s", city_slug)

        except Exception as exc:
            failed += 1
            errors[city_slug] = str(exc)

            logger.exception(
                "health_all_regions_city_failed city=%s error=%s",
                city_slug,
                exc,
            )

    result = _build_result(
        scope="all_regions",
        total=len(all_region_cities),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        start=start,
        errors=errors,
    )

    logger.info(
        "health_all_regions_complete total=%s succeeded=%s failed=%s skipped=%s seconds=%s",
        result.total,
        result.succeeded,
        result.failed,
        result.skipped,
        result.duration_seconds,
    )

    return result


# ---------------------------------------------------------
# Summary Helper
# ---------------------------------------------------------

def result_to_dict(result: HealthIngestResult) -> Dict[str, object]:
    return {
        "scope": result.scope,
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "skipped": result.skipped,
        "duration_seconds": result.duration_seconds,
        "errors": result.errors,
    }