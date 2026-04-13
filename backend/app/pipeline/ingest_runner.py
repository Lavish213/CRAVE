from __future__ import annotations

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