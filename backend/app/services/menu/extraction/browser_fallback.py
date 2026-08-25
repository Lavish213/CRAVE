from __future__ import annotations

import logging
from typing import List, Set

from playwright.sync_api import sync_playwright

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.js.js_menu_payload_adapter import convert_payload_to_menu_items


logger = logging.getLogger(__name__)


TIMEOUT = 15000
MAX_ITEMS = 1500
MAX_PAYLOADS = 50


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _is_json_response(response) -> bool:
    try:
        content_type = response.headers.get("content-type", "").lower()
        return "json" in content_type
    except Exception:
        return False


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


# ---------------------------------------------------------
# Main Browser Extraction
# ---------------------------------------------------------

def extract_with_browser(url: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []
    seen: Set[str] = set()
    captured_payloads = []

    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            # Confirmed live in production: browser.close() previously sat
            # at the end of the happy path only, so any exception between
            # launch() and there -- most commonly page.goto() timing out,
            # which is routine when scraping real restaurant websites --
            # skipped it entirely and leaked the headless Chromium process
            # this function had just launched. menu_worker.py runs this
            # once per place in a batch, so a run touching many places
            # with even a modest timeout rate accumulated leaked browser
            # processes until the container OOM-killed mid-run --
            # orphaning that job_runs row forever (no exception, no
            # traceback, just finished_at staying null) and taking every
            # menu extracted since down with it. try/finally guarantees
            # this runs even when navigation itself is what failed.
            try:
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )

                page = context.new_page()

                # ---------------------------------------------------------
                # Capture API responses
                # ---------------------------------------------------------

                def handle_response(response):

                    if len(captured_payloads) >= MAX_PAYLOADS:
                        return

                    if not _is_json_response(response):
                        return

                    data = _safe_json(response)

                    if not isinstance(data, (dict, list)):
                        return

                    captured_payloads.append(data)

                page.on("response", handle_response)

                # ---------------------------------------------------------
                # Navigate
                # ---------------------------------------------------------

                page.goto(url, timeout=TIMEOUT, wait_until="domcontentloaded")

                # give JS time to fire API calls
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                page.wait_for_timeout(2000)

                # ---------------------------------------------------------
                # Convert payloads → menu items
                # ---------------------------------------------------------

                for payload in captured_payloads:

                    converted = convert_payload_to_menu_items(payload)

                    if not converted:
                        continue

                    for item in converted:

                        key = (
                            f"{(item.name or '').lower()}|"
                            f"{item.price_cents or ''}|"
                            f"{item.section or ''}"
                        )

                        if key in seen:
                            continue

                        seen.add(key)
                        items.append(item)

                        if len(items) >= MAX_ITEMS:
                            break

                    if len(items) >= MAX_ITEMS:
                        break
            finally:
                browser.close()

    except Exception as exc:
        # Was logger.debug -- invisible at the app's default INFO level.
        # A url that hangs/times out here repeatedly (the actual cause of
        # a real multi-hour production stall) produced zero operational
        # signal beyond menu_enrichment quietly never finishing.
        logger.warning(
            "browser_fallback_failed url=%s error=%s",
            url,
            exc,
        )

    logger.info(
        "browser_fallback_items=%s payloads=%s url=%s",
        len(items),
        len(captured_payloads),
        url,
    )

    return items