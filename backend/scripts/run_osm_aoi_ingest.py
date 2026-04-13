from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict

from app.services.discovery.aoi_grid_scanner import AOIGridScanner
from ingest.sources.osm_fetch import fetch_osm_pois


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# AOI (edit for target region)
# ---------------------------------------------------------

AOI = {
    "lat_min": 37.68,
    "lat_max": 37.85,
    "lon_min": -122.55,
    "lon_max": -122.30,
}


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def raw_dir() -> Path:
    path = project_root() / "data" / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------

def run_osm_ingest() -> None:

    scanner = AOIGridScanner()

    cells = scanner.generate_grid(
        lat_min=AOI["lat_min"],
        lat_max=AOI["lat_max"],
        lon_min=AOI["lon_min"],
        lon_max=AOI["lon_max"],
    )

    logger.info("AOI grid cells=%s", len(cells))

    all_results: List[Dict] = []

    for i, cell in enumerate(cells):

        logger.info(
            "Fetching OSM tile %s/%s",
            i + 1,
            len(cells),
        )

        results = fetch_osm_pois(
            lat_min=cell["lat_min"],
            lat_max=cell["lat_max"],
            lon_min=cell["lon_min"],
            lon_max=cell["lon_max"],
        )

        all_results.extend(results)

    logger.info("Total OSM records fetched=%s", len(all_results))

    output_file = raw_dir() / "osm_places.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    logger.info("Saved raw OSM data → %s", output_file)


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

if __name__ == "__main__":
    run_osm_ingest()