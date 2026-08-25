"""
Coverage for toast_browser_scraper.py's fetch_toast_page/fetch_toast_data
-- same Chromium-leak class fixed in browser_fallback.py. Neither
function catches its own exceptions (by design -- callers decide how to
handle a failed fetch), so the fix here only guarantees browser.close()
still runs via try/finally; the original exception still propagates
unchanged.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.services.ingest.toast_browser_scraper import fetch_toast_page, fetch_toast_data


def _make_playwright_mock():
    browser = MagicMock()
    context = MagicMock()
    page = MagicMock()
    context.new_page.return_value = page
    browser.new_context.return_value = context

    p_instance = MagicMock()
    p_instance.chromium.launch.return_value = browser

    cm = MagicMock()
    cm.__enter__.return_value = p_instance
    cm.__exit__.return_value = False
    return cm, browser, page


def test_fetch_toast_page_closes_browser_after_success():
    cm, browser, page = _make_playwright_mock()
    page.content.return_value = "<html>menu</html>"
    with patch(
        "app.services.ingest.toast_browser_scraper.sync_playwright",
        return_value=cm,
    ):
        result = fetch_toast_page("https://order.toasttab.com/x")

    browser.close.assert_called_once()
    assert result == "<html>menu</html>"


def test_fetch_toast_page_closes_browser_even_when_goto_raises():
    """The actual bug: a goto() timeout must not skip cleanup, even
    though the exception is still expected to propagate (this function
    doesn't catch its own failures)."""
    cm, browser, page = _make_playwright_mock()
    page.goto.side_effect = RuntimeError("Timeout 60000ms exceeded")
    with patch(
        "app.services.ingest.toast_browser_scraper.sync_playwright",
        return_value=cm,
    ):
        with pytest.raises(RuntimeError):
            fetch_toast_page("https://order.toasttab.com/x")

    browser.close.assert_called_once()


def test_fetch_toast_data_closes_browser_after_success():
    cm, browser, page = _make_playwright_mock()
    with patch(
        "app.services.ingest.toast_browser_scraper.sync_playwright",
        return_value=cm,
    ), patch(
        "app.services.ingest.toast_browser_scraper._collect_network_payloads",
        return_value=[{"a": 1}],
    ), patch(
        "app.services.ingest.toast_browser_scraper._extract_window_state_payloads",
        return_value=[],
    ):
        result = fetch_toast_data("https://order.toasttab.com/x")

    browser.close.assert_called_once()
    assert result == [{"a": 1}]


def test_fetch_toast_data_closes_browser_even_when_collection_raises():
    cm, browser, page = _make_playwright_mock()
    with patch(
        "app.services.ingest.toast_browser_scraper.sync_playwright",
        return_value=cm,
    ), patch(
        "app.services.ingest.toast_browser_scraper._collect_network_payloads",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError):
            fetch_toast_data("https://order.toasttab.com/x")

    browser.close.assert_called_once()
