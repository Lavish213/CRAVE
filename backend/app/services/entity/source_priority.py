from __future__ import annotations

from typing import Dict


"""
Defines trust ranking for data sources.

Higher number = more trusted
"""

SOURCE_PRIORITY: Dict[str, int] = {

    # -----------------------------------------------------
    # Direct business sources
    # -----------------------------------------------------

    "official_website": 100,
    "schema_org": 95,

    # -----------------------------------------------------
    # Large verified platforms
    # -----------------------------------------------------

    "google_places": 90,
    "apple_maps": 88,

    # -----------------------------------------------------
    # Crowd + aggregator platforms
    # -----------------------------------------------------

    "yelp": 80,
    "tripadvisor": 75,

    # -----------------------------------------------------
    # Open datasets
    # -----------------------------------------------------

    "osm": 60,
    "openaddresses": 40,

    # -----------------------------------------------------
    # Internal sources
    # -----------------------------------------------------

    "crawler": 70,
    "menu_extraction": 65,
    "user_submission": 85,
}


DEFAULT_PRIORITY = 10


def get_source_priority(source: str | None) -> int:

    if not source:
        return DEFAULT_PRIORITY

    return SOURCE_PRIORITY.get(source.lower(), DEFAULT_PRIORITY)


def choose_best_value(values: list[dict]) -> dict | None:
    """
    Select best value based on source priority and confidence.

    Input example:
    [
        {"value": "510-555-1111", "source": "google_places", "confidence": 0.8},
        {"value": "510-555-2222", "source": "official_website", "confidence": 0.9},
    ]
    """

    if not values:
        return None

    best = None
    best_score = -1

    for v in values:

        source = v.get("source")
        confidence = v.get("confidence", 0)

        priority = get_source_priority(source)

        score = priority * 10 + confidence

        if score > best_score:
            best_score = score
            best = v

    return best