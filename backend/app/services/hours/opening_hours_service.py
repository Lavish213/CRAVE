from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo

import opening_hours as opening_hours_lib

from app.services.geo.timezone_lookup import timezone_for_coordinates

logger = logging.getLogger(__name__)

_STATE_TO_STATUS = {
    opening_hours_lib.State.OPEN: "open",
    opening_hours_lib.State.CLOSED: "closed",
    # State.UNKNOWN is itself a real answer some OSM opening_hours strings
    # give on purpose (e.g. an explicit "unknown" rule, or an "or open
    # ..." conditional the library can't resolve) -- folded into the same
    # None ("we don't know") this module already returns for a missing or
    # unparseable string, since neither the API nor the UI should have to
    # tell those two cases apart.
    opening_hours_lib.State.UNKNOWN: None,
}


@dataclass(frozen=True)
class HoursStatus:
    """
    A place's live open/closed status, derived from a raw OSM
    opening_hours string plus its own coordinates (needed to resolve
    which local timezone the string's wall-clock times refer to --
    OSM's opening_hours syntax carries no timezone of its own).

    status is one of "open" / "closed" / None. None ("unknown") covers
    every case where a real answer can't be given honestly: no raw
    string, a string OSM's own grammar can't parse (real-world OSM data
    is frequently malformed), a coordinate pair with no resolvable
    timezone, or the schedule's own explicit "unknown" state -- never
    guessed at or defaulted to open/closed.
    """
    status: Optional[str]
    next_change: Optional[datetime]
    raw: Optional[str]


_NO_DATA = HoursStatus(status=None, next_change=None, raw=None)


def compute_hours_status(
    raw_opening_hours: Optional[str],
    *,
    lat: Optional[float],
    lng: Optional[float],
    now: Optional[datetime] = None,
) -> HoursStatus:
    """
    Compute live open/closed status from an OSM-syntax opening_hours
    string. Returns HoursStatus(status=None, ...) -- "unknown", never a
    guessed open/closed -- when the string is missing, malformed, or a
    timezone can't be resolved from lat/lng. Never raises: every
    failure mode collapses to "unknown" rather than a 500.
    """
    raw = (raw_opening_hours or "").strip()
    if not raw or lat is None or lng is None:
        return _NO_DATA

    tz_name = timezone_for_coordinates(lat, lng)
    if not tz_name:
        logger.debug("hours_status_no_timezone lat=%s lng=%s", lat, lng)
        return HoursStatus(status=None, next_change=None, raw=raw)

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.debug("hours_status_bad_timezone tz=%s", tz_name)
        return HoursStatus(status=None, next_change=None, raw=raw)

    local_now = (now or datetime.now(dt_timezone.utc)).astimezone(tz)

    try:
        parsed = opening_hours_lib.OpeningHours(raw)
        state, _comment = parsed.state(local_now)
        next_change = parsed.next_change(local_now)
    except Exception as exc:
        logger.debug("hours_status_parse_failed raw=%r error=%s", raw, exc)
        return HoursStatus(status=None, next_change=None, raw=raw)

    return HoursStatus(
        status=_STATE_TO_STATUS.get(state),
        next_change=next_change,
        raw=raw,
    )
