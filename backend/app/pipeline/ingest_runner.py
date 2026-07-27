from __future__ import annotations

# DEPRECATED / UNUSED: superseded by app.services.discovery.pipeline_v2
# (run_discovery_pipeline_v2), which is what app/scheduler.py's discovery job
# and scripts/run_google_ingest.py actually call. A grep across the entire
# backend/ tree found the only importer of this module to be
# app/pipeline/aoi_scan_job_runner.py, which is itself unreferenced by
# anything outside this dead app/pipeline/* cluster.
# Kept here for reference only — not wired up. Safe to delete if no longer needed.

import logging
from typing import Dict, Iterable, List

from app.pipeline.candidate_builder import CandidateBuilder
from app.pipeline.candidate_cluster_builder import CandidateClusterBuilder
from app.pipeline.promotion_engine import PromotionEngine


logger = logging.getLogger(__name__)


class IngestRunner:
    """
    End-to-end ingestion pipeline.

    Raw records
        ↓
    CandidateBuilder
        ↓
    CandidateClusterBuilder
        ↓
    PromotionEngine
        ↓
    Restaurant entities
    """

    def __init__(self) -> None:

        self.candidate_builder = CandidateBuilder()
        self.cluster_builder = CandidateClusterBuilder()
        self.promotion_engine = PromotionEngine()

    # -----------------------------------------------------
    # Pipeline entrypoint
    # -----------------------------------------------------

    def run(
        self,
        records: Iterable[Dict],
        *,
        source: str,
    ) -> List[Dict]:

        logger.info(
            "ingest_pipeline_start source=%s",
            source,
        )

        # ---------------------------------------------
        # build candidates
        # ---------------------------------------------

        candidates = self.candidate_builder.build_candidates(
            records,
            source=source,
        )

        # ---------------------------------------------
        # cluster duplicates
        # ---------------------------------------------

        clusters = self.cluster_builder.cluster_candidates(
            candidates
        )

        # ---------------------------------------------
        # promote entities
        # ---------------------------------------------

        entities = self.promotion_engine.promote_clusters(
            clusters
        )

        logger.info(
            "ingest_pipeline_complete source=%s entities=%s",
            source,
            len(entities),
        )

        return entities