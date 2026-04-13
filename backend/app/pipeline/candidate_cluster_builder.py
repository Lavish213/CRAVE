from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Optional

from app.services.entity.entity_matcher import entity_match


logger = logging.getLogger(__name__)


MAX_CLUSTER_SIZE = 100
MAX_CLUSTERS = 2000


def _safe_float(value) -> Optional[float]:

    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


class CandidateClusterBuilder:
    """
    Groups candidate records that likely represent
    the same restaurant location.

    Designed to remain deterministic and bounded
    even for large candidate batches.
    """

    def cluster_candidates(
        self,
        candidates: List[dict],
    ) -> List[List[dict]]:

        if not candidates:
            return []

        clusters: List[List[dict]] = []

        spatial_buckets: Dict[Tuple[int, int], List[List[dict]]] = {}

        for candidate in candidates:

            try:
                bucket_key = self._spatial_bucket(candidate)
            except Exception:
                bucket_key = (0, 0)

            candidate_clusters = spatial_buckets.get(bucket_key)

            if candidate_clusters is None:

                candidate_clusters = []
                spatial_buckets[bucket_key] = candidate_clusters

            placed = False

            for cluster in candidate_clusters:

                if len(cluster) >= MAX_CLUSTER_SIZE:
                    continue

                if self._matches_cluster(candidate, cluster):

                    cluster.append(candidate)
                    placed = True
                    break

            if not placed:

                if len(clusters) >= MAX_CLUSTERS:

                    logger.warning(
                        "cluster_limit_reached clusters=%s candidates=%s",
                        len(clusters),
                        len(candidates),
                    )

                    break

                new_cluster = [candidate]

                clusters.append(new_cluster)
                candidate_clusters.append(new_cluster)

        logger.info(
            "candidate_clusters_built clusters=%s candidates=%s",
            len(clusters),
            len(candidates),
        )

        return clusters

    # -----------------------------------------------------
    # Spatial Bucketing
    # -----------------------------------------------------

    def _spatial_bucket(
        self,
        candidate: dict,
    ) -> Tuple[int, int]:

        lat = _safe_float(candidate.get("lat"))
        lng = _safe_float(candidate.get("lng") or candidate.get("lon"))

        if lat is None or lng is None:
            return (0, 0)

        # 0.001 ≈ 110 meters
        return (int(lat * 1000), int(lng * 1000))

    # -----------------------------------------------------
    # Matching logic
    # -----------------------------------------------------

    def _matches_cluster(
        self,
        candidate: dict,
        cluster: List[dict],
    ) -> bool:

        if not cluster:
            return False

        representative = cluster[0]

        try:

            if entity_match(representative, candidate):
                return True

        except Exception as exc:

            logger.debug(
                "cluster_match_failed error=%s",
                exc,
            )

        return False