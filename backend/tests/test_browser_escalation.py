"""
Coverage for browser_escalation.py -- same Chromium-leak class fixed in
browser_fallback.py (see that module's own test file's docstring).
sync_playwright is imported inside fetch_with_browser() itself, not at
module level, so it has to be patched at its real source
(playwright.sync_api.sync_playwright) rather than as a module attribute.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.network.browser_escalation import fetch_with_browser


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
    return cm, browser, context, page


def test_browser_and_context_closed_after_success():
    cm, browser, context, page = _make_playwright_mock()
    page.content.return_value = "<html>hello</html>"
    with patch("playwright.sync_api.sync_playwright", return_value=cm):
        fetch_with_browser("https://example.com")

    browser.close.assert_called_once()
    context.close.assert_called_once()


def test_browser_and_context_closed_even_when_content_raises():
    """The actual bug: anything failing between launch() and content()
    must not skip cleanup."""
    cm, browser, context, page = _make_playwright_mock()
    page.content.side_effect = RuntimeError("page crashed")
    with patch("playwright.sync_api.sync_playwright", return_value=cm):
        result = fetch_with_browser("https://example.com")

    browser.close.assert_called_once()
    context.close.assert_called_once()
    assert result is None


def test_browser_closed_even_when_both_goto_attempts_fail():
    from playwright.sync_api import TimeoutError as PWTimeoutError

    cm, browser, context, page = _make_playwright_mock()
    page.goto.side_effect = PWTimeoutError("timed out")
    with patch("playwright.sync_api.sync_playwright", return_value=cm):
        result = fetch_with_browser("https://example.com")

    browser.close.assert_called_once()
    assert result is None
