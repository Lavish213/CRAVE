from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.discovery_candidate import DiscoveryCandidate

from app.services.aoi.aoi_candidate_selector import select_candidates
from app.pipeline.candidate_cluster_builder import CandidateClusterBuilder
from app.services.truth.place_resolver import PlaceResolver


logger = logging.getLogger(__name__)


DEFAULT_LIMIT = 50


class DiscoveryCandidateWorker:
    """
    Runs the discovery promotion pipeline.

    Pipeline

    select candidates
        ↓
    cluster candidates
        ↓
    resolve clusters → places
        ↓
    mark candidates resolved

    This worker orchestrates the discovery system but
    does not contain heavy logic itself.
    """

    def run(
        self,
        db: Session,
        *,
        places: List[Place],
        limit: int = DEFAULT_LIMIT,
    ) -> int:

        # -------------------------------------------------
        # Select candidates
        # -------------------------------------------------

        candidates: List[DiscoveryCandidate] = select_candidates(
            places=places,
            limit=limit,
        )

        if not candidates:

            logger.info(
                "discovery_worker_no_candidates"
            )

            return 0

        logger.info(
            "discovery_worker_candidates_loaded count=%s",
            len(candidates),
        )

        # -------------------------------------------------
        # Cluster candidates
        # -------------------------------------------------

        cluster_builder = CandidateClusterBuilder()

        clusters = cluster_builder.cluster_candidates(candidates)

        if not clusters:

            logger.info(
                "discovery_worker_no_clusters"
            )

            return 0

        logger.info(
            "discovery_worker_clusters_created clusters=%s",
            len(clusters),
        )

        # -------------------------------------------------
        # Resolve clusters → places
        # -------------------------------------------------

        resolver = PlaceResolver()

        promoted = 0
        failed = 0

        for cluster in clusters:

            if not cluster:
                continue

            try:

                place = resolver.resolve_cluster(
                    db=db,
                    cluster=cluster,
                )

                if place:
                    promoted += 1

            except Exception as exc:

                failed += 1

                logger.error(
                    "candidate_resolution_failed cluster_size=%s error=%s",
                    len(cluster),
                    exc,
                )

        # -------------------------------------------------
        # Logging
        # -------------------------------------------------

        logger.info(
            "discovery_worker_complete promoted=%s failed=%s clusters=%s candidates=%s",
            promoted,
            failed,
            len(clusters),
            len(candidates),
        )

        return promoted