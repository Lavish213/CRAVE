from __future__ import annotations

from app.services.geo.timezone_lookup import timezone_for_coordinates


def test_resolves_known_city_coordinates():
    assert timezone_for_coordinates(37.7749, -122.4194) == "America/Los_Angeles"
    assert timezone_for_coordinates(40.7128, -74.0060) == "America/New_York"


def test_never_raises_on_bad_input():
    # Out-of-range coordinates must degrade to None, not raise -- a
    # timezone lookup failure is not a reason to break the caller.
    assert timezone_for_coordinates(999.0, 999.0) is None
