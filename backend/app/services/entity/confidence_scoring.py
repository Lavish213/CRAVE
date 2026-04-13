from __future__ import annotations

import logging
from typing import Dict, List


logger = logging.getLogger(__name__)


MAX_SCORE = 1.0


def score_entity_confidence(
    cluster: List[Dict],
) -> float:
    """
    Score confidence that a cluster represents
    a real restaurant entity.
    """

    if not cluster:
        return 0.0

    score = 0.4

    # multiple sources increases confidence
    sources = set()

    for item in cluster:
        src = item.get("source")
        if src:
            sources.add(src)

    if len(sources) >= 2:
        score += 0.2

    if len(sources) >= 3:
        score += 0.1

    # website presence
    for item in cluster:
        if item.get("website"):
            score += 0.15
            break

    # phone presence
    for item in cluster:
        if item.get("phone"):
            score += 0.1
            break

    if score > MAX_SCORE:
        score = MAX_SCORE

    logger.debug(
        "entity_confidence_scored size=%s score=%.3f",
        len(cluster),
        score,
    )

    return score