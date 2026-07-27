from __future__ import annotations

# DEPRECATED / UNUSED: superseded by app.services.discovery.pipeline_v2
# (run_discovery_pipeline_v2), which is what app/scheduler.py's discovery job
# and scripts/run_google_ingest.py actually call. A grep across the entire
# backend/ tree found zero imports of app.pipeline.aoi_scan_job_runner from
# anywhere outside this dead app/pipeline/* cluster (it is the top of a
# self-contained chain: aoi_scan_job_runner -> ingest_runner ->
# candidate_builder / candidate_cluster_builder / promotion_engine, none of
# which anything else references either).
# Kept here for reference only — not wired up. Safe to delete if no longer needed.

import logging
from typing import Dict, Iterable, List

from app.services.discovery.aoi_grid_scanner import AOIGridScanner
from app.services.discovery.osm_overpass import fetch_osm_pois

from app.pipeline.ingest_runner import IngestRunner


logger = logging.getLogger(__name__)


class AOIScanJobRunner:
    """
    Runs an Area Of Interest (AOI) discovery scan.

    Steps
    -----
    1. Generate grid cells
    2. Query discovery sources (OSM etc)
    3. Feed results into ingest pipeline
    """

    def __init__(self) -> None:

        self.grid_scanner = AOIGridScanner()
        self.ingest_runner = IngestRunner()

    # -----------------------------------------------------
    # Entry
    # -----------------------------------------------------

    def run_scan(
        self,
        *,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
    ) -> List[Dict]:

        logger.info(
            "aoi_scan_start lat_min=%s lat_max=%s lon_min=%s lon_max=%s",
            lat_min,
            lat_max,
            lon_min,
            lon_max,
        )

        all_entities: List[Dict] = []

        cells = self.grid_scanner.generate_grid(
            lat_min=lat_min,
            lat_max=lat_max,
            lon_min=lon_min,
            lon_max=lon_max,
        )

        for cell in cells:

            try:

                records = fetch_osm_pois(
                    lat_min=cell["lat_min"],
                    lat_max=cell["lat_max"],
                    lon_min=cell["lon_min"],
                    lon_max=cell["lon_max"],
                )

                entities = self.ingest_runner.run(
                    records,
                    source="osm",
                )

                all_entities.extend(entities)

            except Exception as exc:

                logger.debug(
                    "aoi_cell_failed cell=%s error=%s",
                    cell,
                    exc,
                )

        logger.info(
            "aoi_scan_complete entities=%s cells=%s",
            len(all_entities),
            len(cells),
        )

        return all_entities