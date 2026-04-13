from __future__ import annotations

import logging
import sys
import time
from typing import List

from config.city_loader import load_region_map
from config.health_datasets import get_health_dataset

from scripts.run_arcgis_ingest import run_arcgis_ingest
from scripts.run_socrata_ingest import run_socrata_ingest


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ---------------------------------------------------------
# Dataset Runner Selector
# ---------------------------------------------------------

def _run_city_dataset(city_slug: str) -> None:

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


# ---------------------------------------------------------
# Region Runner
# ---------------------------------------------------------

def run_region(region_name: str) -> None:

    region_map = load_region_map()

    if region_name not in region_map:

        available = ", ".join(sorted(region_map.keys()))

        raise RuntimeError(
            f"Region '{region_name}' not found. Available regions: {available}"
        )

    cities: List[str] = region_map[region_name]

    logger.info(
        "health_region_start region=%s cities=%s",
        region_name,
        len(cities),
    )

    start = time.time()

    success = 0
    failed = 0

    for city in cities:

        try:

            logger.info(
                "health_region_city_start city=%s",
                city,
            )

            _run_city_dataset(city)

            success += 1

        except Exception as exc:

            failed += 1

            logger.exception(
                "health_region_city_failed city=%s error=%s",
                city,
                exc,
            )

    elapsed = round(time.time() - start, 2)

    logger.info(
        "health_region_complete region=%s success=%s failed=%s seconds=%s",
        region_name,
        success,
        failed,
        elapsed,
    )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    if len(sys.argv) < 2:

        print("Usage:")
        print("python scripts/run_health_region.py <region_name>")

        sys.exit(1)

    region_name = sys.argv[1].lower().strip()

    run_region(region_name)


if __name__ == "__main__":
    main()