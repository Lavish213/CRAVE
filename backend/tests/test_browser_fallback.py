"""
Coverage for browser_fallback.py -- specifically the resource-leak fix
confirmed live in production: browser.close() previously sat only at the
end of the happy path, so a navigation timeout (routine when scraping
real restaurant websites) skipped it entirely and leaked the headless
Chromium process. menu_worker.py calls this once per place in a batch;
enough leaked timeouts in one run accumulated until the container
OOM-killed mid-run, which is why menu_enrichment stopped completing at
all in production (job_runs rows stuck at finished_at=null, no error).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.menu.extraction.browser_fallback import extract_with_browser


def _make_playwright_mock(*, goto_side_effect=None):
    browser = MagicMock()
    context = MagicMock()
    page = MagicMock()
    context.new_page.return_value = page
    browser.new_context.return_value = context
    if goto_side_effect is not None:
        page.goto.side_effect = goto_side_effect

    p_instance = MagicMock()
    p_instance.chromium.launch.return_value = browser

    cm = MagicMock()
    cm.__enter__.return_value = p_instance
    cm.__exit__.return_value = False
    return cm, browser


def test_browser_is_closed_after_successful_extraction():
    cm, browser = _make_playwright_mock()
    with patch(
        "app.services.menu.extraction.browser_fallback.sync_playwright",
        return_value=cm,
    ):
        extract_with_browser("https://example.com/menu")

    browser.close.assert_called_once()


def test_browser_is_closed_even_when_navigation_times_out():
    """The actual bug: a page.goto() timeout must not leak the browser."""
    cm, browser = _make_playwright_mock(
        goto_side_effect=RuntimeError("Timeout 15000ms exceeded"),
    )
    with patch(
        "app.services.menu.extraction.browser_fallback.sync_playwright",
        return_value=cm,
    ):
        items = extract_with_browser("https://example.com/menu")

    browser.close.assert_called_once()
    assert items == []


def test_browser_is_closed_when_response_handling_raises():
    """Any other mid-page exception must not skip cleanup either."""
    cm, browser = _make_playwright_mock()
    cm.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.side_effect = RuntimeError(
        "boom"
    )
    with patch(
        "app.services.menu.extraction.browser_fallback.sync_playwright",
        return_value=cm,
    ):
        items = extract_with_browser("https://example.com/menu")

    browser.close.assert_called_once()
    assert items == []


def test_launch_failure_itself_does_not_raise():
    """If launch() itself fails, there's no browser to close -- must not crash."""
    p_instance = MagicMock()
    p_instance.chromium.launch.side_effect = RuntimeError("no chromium binary")
    cm = MagicMock()
    cm.__enter__.return_value = p_instance
    cm.__exit__.return_value = False

    with patch(
        "app.services.menu.extraction.browser_fallback.sync_playwright",
        return_value=cm,
    ):
        items = extract_with_browser("https://example.com/menu")

    assert items == []
