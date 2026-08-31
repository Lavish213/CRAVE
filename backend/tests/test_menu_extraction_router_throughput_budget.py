"""Coverage for the wall-clock probe budgets in menu_extraction_router.py.

Confirmed root cause of a production run exceeding 17 minutes: each
candidate API endpoint gets its own ~8s network timeout
(api_menu_extractor.REQUEST_TIMEOUT), and MAX_API_ENDPOINTS alone doesn't
bound total wall-clock time -- a place with many slow/dead candidates
could burn minutes on that one sub-stage. These tests prove the budget
actually stops probing further candidates once spent, using a fake clock
rather than real sleeps.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.menu.menu_extraction_router import (
    _safe_api_extract,
    _safe_iframe_extract,
)


class _FakeClock:
    """Advances by a fixed step every call, so N calls == N * step seconds
    elapsed without any real sleeping."""

    def __init__(self, step: float):
        self.step = step
        self.now = 0.0

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def test_api_probe_stops_once_time_budget_is_spent():
    endpoints = [f"https://restaurant.test/api/candidate-{i}" for i in range(20)]
    clock = _FakeClock(step=6.0)  # each iteration "costs" 6s of the 20s budget

    with patch(
        "app.services.menu.menu_extraction_router.discover_api_endpoints",
        return_value=endpoints,
    ), patch(
        "app.services.menu.menu_extraction_router.time.monotonic",
        side_effect=clock,
    ), patch(
        "app.services.menu.menu_extraction_router.extract_api_menu",
        return_value=[],
    ) as mock_extract:
        _safe_api_extract("<html>menu</html>", "https://restaurant.test")

    # Budget is 20s at 6s/iteration: the deadline check consumes one tick
    # up front, then each loop iteration consumes another -- verify it
    # stops well short of trying all 20 endpoints, not that every one ran.
    assert mock_extract.call_count < len(endpoints)
    assert mock_extract.call_count > 0


def test_api_probe_tries_every_endpoint_when_well_under_budget():
    endpoints = [f"https://restaurant.test/api/candidate-{i}" for i in range(5)]
    clock = _FakeClock(step=0.1)  # fast candidates, nowhere near the 20s budget

    with patch(
        "app.services.menu.menu_extraction_router.discover_api_endpoints",
        return_value=endpoints,
    ), patch(
        "app.services.menu.menu_extraction_router.time.monotonic",
        side_effect=clock,
    ), patch(
        "app.services.menu.menu_extraction_router.extract_api_menu",
        return_value=[],
    ) as mock_extract:
        _safe_api_extract("<html>menu</html>", "https://restaurant.test")

    assert mock_extract.call_count == len(endpoints)


def test_iframe_probe_stops_once_time_budget_is_spent():
    iframe_urls = [f"https://restaurant.test/embed-{i}" for i in range(10)]
    clock = _FakeClock(step=5.0)  # each iteration "costs" 5s of the 15s budget

    with patch(
        "app.services.menu.menu_extraction_router.detect_menu_iframes",
        return_value=iframe_urls,
    ), patch(
        "app.services.menu.menu_extraction_router.time.monotonic",
        side_effect=clock,
    ), patch(
        "app.services.menu.menu_extraction_router.fetch",
    ) as mock_fetch:
        _safe_iframe_extract("<html>menu</html>", "https://restaurant.test")

    assert mock_fetch.call_count < len(iframe_urls)
    assert mock_fetch.call_count > 0
