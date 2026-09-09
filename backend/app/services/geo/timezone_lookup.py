from __future__ import annotations

from functools import lru_cache
from typing import Optional

from timezonefinder import TimezoneFinder

# TimezoneFinder() loads its whole boundary dataset into memory (~50MB) —
# expensive enough that this must be a process-wide singleton, not
# constructed per lookup. Offline/deterministic: resolves lat/lng -> IANA
# timezone with no network call and no API key, unlike every hosted
# geocoding/timezone API.
_finder: Optional[TimezoneFinder] = None


def _get_finder() -> TimezoneFinder:
    global _finder
    if _finder is None:
        _finder = TimezoneFinder()
    return _finder


@lru_cache(maxsize=4096)
def timezone_for_coordinates(lat: float, lng: float) -> Optional[str]:
    """
    Resolve an IANA timezone name (e.g. "America/Los_Angeles") for a
    lat/lng pair. Returns None over open ocean or other areas with no
    assigned timezone -- callers must treat that as "unknown", never
    default to UTC or the server's own timezone, since either would
    silently mislabel a place's real local hours.

    Cached (lru_cache): the same handful of coordinates get resolved
    repeatedly across a batch backfill run, and the lookup, while
    offline, is not free (a polygon containment search).
    """
    try:
        return _get_finder().timezone_at(lat=lat, lng=lng)
    except Exception:
        return None
