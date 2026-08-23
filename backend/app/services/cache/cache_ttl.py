from __future__ import annotations

from typing import Optional


FEED_TTL = 300          # 5 minutes

# Previously 30-60s -- far shorter than how often the underlying data
# actually changes (discovery runs every 5min, score_recompute every
# 15min, ranking_update every 30min), and combined with map_key()'s old
# 4-decimal coordinate rounding (~11m grid cells), two different requests
# almost never landed on the same key anyway. Now that map_key() rounds to
# a coarser ~1.1km grid (see cache_keys.py), a longer TTL actually gets
# used instead of expiring before a second request could ever reuse it.
MAP_TTL = 180           # 3 minutes

# search_cache_key() now includes a grid-rounded lat/lng (fixing a real
# cache-key bug -- distance-based ordering depends on the searcher's
# location, but the key never accounted for it, so one caller's
# location-sorted results could be served straight back to a different
# caller). Bumped alongside MAP_TTL for the same reason: the underlying
# rank_score/proximity data changes on the order of minutes, not seconds.
SEARCH_TTL = 180
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
        return 120

    if radius_km <= 5:
        return MAP_TTL

    return 300


def search_ttl(
    *,
    query: str,
) -> int:

    q = (query or "").strip()

    if len(q) <= 3:
        return 90

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