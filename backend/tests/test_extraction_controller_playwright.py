"""
Coverage for ExtractionController._fetch_with_playwright -- same
Chromium-leak class fixed in browser_fallback.py. sync_playwright is
imported inside the method itself, so it's patched at its real source
(playwright.sync_api.sync_playwright).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.menu.extraction_controller import ExtractionController


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


def test_browser_closed_after_success():
    cm, browser, page = _make_playwright_mock()
    page.content.return_value = "x" * 600
    controller = ExtractionController()
    with patch("playwright.sync_api.sync_playwright", return_value=cm):
        result = controller._fetch_with_playwright("https://example.com/menu")

    browser.close.assert_called_once()
    assert result == "x" * 600


def test_browser_closed_even_when_content_raises():
    """The actual bug: page.content() failing must not skip cleanup."""
    cm, browser, page = _make_playwright_mock()
    page.content.side_effect = RuntimeError("page crashed")
    controller = ExtractionController()
    with patch("playwright.sync_api.sync_playwright", return_value=cm):
        result = controller._fetch_with_playwright("https://example.com/menu")

    browser.close.assert_called_once()
    assert result is None
