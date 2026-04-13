from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.services.entity.confidence_scoring import score_entity_confidence


logger = logging.getLogger(__name__)


MAX_PROMOTIONS = 2000
MIN_PROMOTION_SCORE = 0.65


class PromotionEngine:
    """
    Decides which clustered candidates should be promoted
    into canonical Restaurant entities.
    """

    def promote_clusters(
        self,
        clusters: List[List[dict]],
    ) -> List[Dict]:

        promoted: List[Dict] = []

        for cluster in clusters:

            try:

                entity = self._promote_cluster(cluster)

                if not entity:
                    continue

                promoted.append(entity)

            except Exception as exc:

                logger.debug(
                    "cluster_promotion_failed error=%s",
                    exc,
                )

            if len(promoted) >= MAX_PROMOTIONS:
                break

        logger.info(
            "entities_promoted count=%s clusters=%s",
            len(promoted),
            len(clusters),
        )

        return promoted

    # -----------------------------------------------------
    # Promotion logic
    # -----------------------------------------------------

    def _promote_cluster(
        self,
        cluster: List[dict],
    ) -> Optional[Dict]:

        if not cluster:
            return None

        confidence = score_entity_confidence(cluster)

        if confidence < MIN_PROMOTION_SCORE:
            return None

        best = cluster[0]

        entity = {
            "name": best.get("name"),
            "normalized_name": best.get("normalized_name"),
            "address": best.get("address"),
            "normalized_address": best.get("normalized_address"),
            "lat": best.get("lat"),
            "lon": best.get("lon"),
            "phone": best.get("phone"),
            "website": best.get("website"),
            "confidence": confidence,
            "sources": [c.get("source") for c in cluster],
            "cluster_size": len(cluster),
        }

        return entity