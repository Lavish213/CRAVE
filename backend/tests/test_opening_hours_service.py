"""
Coverage for app/services/hours/opening_hours_service.py.

compute_hours_status() must never crash and never fabricate an open/
closed answer it doesn't actually have -- OSM's real-world opening_hours
data is frequently malformed, and the library used to parse it
(opening_hours_py) raises on a bad string rather than degrading
gracefully on its own.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.hours.opening_hours_service import compute_hours_status

# San Francisco. 2026-09-09 is a Wednesday.
SF_LAT, SF_LNG = 37.7749, -122.4194


def test_open_during_scheduled_hours():
    # 16:00 UTC on a Wednesday = 09:00 America/Los_Angeles (PDT, UTC-7).
    now = datetime(2026, 9, 9, 16, 0, 0, tzinfo=timezone.utc)

    result = compute_hours_status(
        "Mo-Fr 09:00-17:00", lat=SF_LAT, lng=SF_LNG, now=now,
    )

    assert result.status == "open"
    assert result.next_change is not None
    assert result.raw == "Mo-Fr 09:00-17:00"


def test_closed_outside_scheduled_hours():
    # 03:00 UTC on 2026-09-09 = 20:00 America/Los_Angeles on 2026-09-08
    # (Tuesday), an hour after Mo-Fr 09:00-17:00 has closed for the day.
    now = datetime(2026, 9, 9, 3, 0, 0, tzinfo=timezone.utc)

    result = compute_hours_status(
        "Mo-Fr 09:00-17:00", lat=SF_LAT, lng=SF_LNG, now=now,
    )

    assert result.status == "closed"


def test_malformed_opening_hours_string_is_unknown_not_a_crash():
    result = compute_hours_status(
        "totally not a real schedule ###", lat=SF_LAT, lng=SF_LNG,
    )

    assert result.status is None
    assert result.raw == "totally not a real schedule ###"


def test_missing_raw_string_is_unknown():
    result = compute_hours_status(None, lat=SF_LAT, lng=SF_LNG)

    assert result.status is None
    assert result.next_change is None
    assert result.raw is None


def test_missing_coordinates_is_unknown():
    result = compute_hours_status("Mo-Fr 09:00-17:00", lat=None, lng=None)

    assert result.status is None


def test_explicit_unknown_state_in_the_schedule_itself_is_unknown():
    # Same instant as test_open_during_scheduled_hours (09:00 local, inside
    # the rule's own range) -- but this rule marks that range "unknown"
    # rather than open, and that must come through as None, not "open".
    now = datetime(2026, 9, 9, 16, 0, 0, tzinfo=timezone.utc)

    result = compute_hours_status(
        "Mo-Fr 09:00-17:00 unknown", lat=SF_LAT, lng=SF_LNG, now=now,
    )

    assert result.status is None
