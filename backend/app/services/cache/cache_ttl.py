from __future__ import annotations

from typing import Optional


FEED_TTL = 300          # 5 minutes
MAP_TTL = 45
SEARCH_TTL = 120
PLACE_DETAIL_TTL = 300
PLACE_MENU_TTL = 1800   # 30 minutes — menu changes infrequently

CATEGORIES_TTL = 3600
CITIES_TTL = 3600

# Negative-result cache TTLs (provider probe / blocked domain)
NEGATIVE_PROBE_TTL_TIMEOUT = 1800     # 30 min — timeouts may recover
NEGATIVE_PROBE_TTL_BLOCKED = 43200    # 12 h  — 4xx / captcha / blocked HTML
NEGATIVE_PROBE_TTL_DEFAULT = 3600     # 1 h   — all other fetch failures

EXTRACTION_RESULT_TTL = 14400         # 4 h — prevent redundant re-extraction


def feed_ttl(
    *,
    city_id: Optional[str],
) -> int:
    if city_id:
        return FEED_TTL
    return FEED_TTL


def map_ttl(
    *,
    radius_km: float,
) -> int:

    if radius_km <= 2:
        return 30

    if radius_km <= 5:
        return MAP_TTL

    return 60


def search_ttl(
    *,
    query: str,
) -> int:

    q = (query or "").strip()

    if len(q) <= 3:
        return 60

    return SEARCH_TTL


def place_detail_ttl(
    *,
    place_id: str,
) -> int:
    return PLACE_DETAIL_TTL


def categories_ttl() -> int:
    return CATEGORIES_TTL


def cities_ttl() -> int:
    return CITIES_TTL