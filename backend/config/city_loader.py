from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

CITY_DATA_DIR = BASE_DIR / "data" / "cities"


# ---------------------------------------------------------
# Region Loader
# ---------------------------------------------------------

def _load_region_file(path: Path) -> List[str]:

    try:

        with path.open("r", encoding="utf-8") as f:

            data = json.load(f)

    except Exception as exc:

        logger.warning(
            "city_loader_failed path=%s error=%s",
            path,
            exc,
        )

        return []

    if not isinstance(data, dict):

        logger.warning("city_loader_invalid_format path=%s", path)

        return []

    cities = data.get("cities")

    if not isinstance(cities, list):

        logger.warning("city_loader_missing_cities path=%s", path)

        return []

    normalized: List[str] = []

    for city in cities:

        if not city:
            continue

        slug = str(city).strip().lower()

        if slug:
            normalized.append(slug)

    return normalized


# ---------------------------------------------------------
# Load All Regions
# ---------------------------------------------------------

def load_all_cities() -> List[str]:

    if not CITY_DATA_DIR.exists():

        logger.warning(
            "city_loader_missing_directory path=%s",
            CITY_DATA_DIR,
        )

        return []

    cities: Set[str] = set()

    files = sorted(CITY_DATA_DIR.glob("*.json"))

    if not files:

        logger.warning("city_loader_no_region_files")

        return []

    for path in files:

        region_cities = _load_region_file(path)

        for city in region_cities:
            cities.add(city)

    result = sorted(cities)

    logger.info(
        "city_loader_loaded regions=%s cities=%s",
        len(files),
        len(result),
    )

    return result


# ---------------------------------------------------------
# Load Region → Cities Map
# ---------------------------------------------------------

def load_region_map() -> Dict[str, List[str]]:

    region_map: Dict[str, List[str]] = {}

    if not CITY_DATA_DIR.exists():
        return region_map

    for path in sorted(CITY_DATA_DIR.glob("*.json")):

        region = path.stem

        cities = _load_region_file(path)

        if cities:
            region_map[region] = cities

    logger.info(
        "city_loader_regions_loaded regions=%s",
        len(region_map),
    )

    return region_map


# ---------------------------------------------------------
# Region Lookup
# ---------------------------------------------------------

def get_region_for_city(city_slug: str) -> Optional[str]:
    """
    Return the region a city belongs to.

    Useful for ingestion routing and debugging.
    """

    city_slug = city_slug.lower().strip()

    region_map = load_region_map()

    for region, cities in region_map.items():

        if city_slug in cities:
            return region

    return None


# ---------------------------------------------------------
# Region → City Validation
# ---------------------------------------------------------

def validate_city_regions() -> None:

    region_map = load_region_map()

    seen: Set[str] = set()

    duplicates: Set[str] = set()

    for region, cities in region_map.items():

        for city in cities:

            if city in seen:
                duplicates.add(city)

            seen.add(city)

    if duplicates:

        logger.warning(
            "city_loader_duplicate_cities duplicates=%s",
            sorted(duplicates),
        )


# ---------------------------------------------------------
# Registry Consistency Check
# ---------------------------------------------------------

def validate_against_registry(registry_cities: List[str]) -> None:
    """
    Validate that city loader and dataset registry match.

    Helps detect missing dataset configs.
    """

    loader_cities = set(load_all_cities())
    registry_cities = set(registry_cities)

    missing_configs = loader_cities - registry_cities
    missing_regions = registry_cities - loader_cities

    if missing_configs:
        logger.warning(
            "city_loader_missing_dataset_configs cities=%s",
            sorted(missing_configs),
        )

    if missing_regions:
        logger.warning(
            "city_loader_registry_not_in_regions cities=%s",
            sorted(missing_regions),
        )


# ---------------------------------------------------------
# CLI Debug Tool
# ---------------------------------------------------------

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    cities = load_all_cities()

    print()

    print("Cities loaded:", len(cities))

    for city in cities:
        print(city)