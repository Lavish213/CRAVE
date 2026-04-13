from __future__ import annotations

import logging
from typing import Optional

from playwright.sync_api import Error, TimeoutError, sync_playwright


logger = logging.getLogger(__name__)


BROWSER_TIMEOUT_MS = 20000
WAIT_AFTER_LOAD_MS = 2500


def should_browser_escalate(
    *,
    reason: Optional[str],
    attempt: int,
) -> bool:
    normalized = (reason or "").strip().lower()

    if attempt < 2:
        return False

    if normalized in {
        "hard_403",
        "html_block",
        "bot_challenge",
        "empty_html",
        "redirect_loop",
        "redirect_limit",
    }:
        return True

    return False


def fetch_with_browser(
    url: str,
    *,
    referer: Optional[str] = None,
) -> Optional[str]:
    if not url:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                java_script_enabled=True,
                viewport={"width": 1280, "height": 800},
                device_scale_factor=1,
                is_mobile=False,
            )

            page = context.new_page()

            extra_headers = {
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }

            if referer:
                extra_headers["Referer"] = referer

            page.set_extra_http_headers(extra_headers)

            try:
                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=BROWSER_TIMEOUT_MS,
                )
            except TimeoutError:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=BROWSER_TIMEOUT_MS,
                )

            try:
                page.wait_for_selector("body", timeout=5000)
            except Exception:
                pass

            page.wait_for_timeout(WAIT_AFTER_LOAD_MS)

            html = page.content()

            try:
                context.close()
            except Exception:
                pass

            try:
                browser.close()
            except Exception:
                pass

            if not html or not html.strip():
                return None

            lowered = html.lower()

            if any(
                token in lowered
                for token in (
                    "captcha",
                    "access denied",
                    "verify you are human",
                    "cloudflare",
                )
            ):
                logger.debug("browser_still_blocked url=%s", url)
                return None

            return html

    except TimeoutError:
        logger.debug("browser_escalation_timeout url=%s", url)
        return None

    except Error as exc:
        logger.debug("browser_escalation_playwright_error url=%s error=%s", url, exc)
        return None

    except Exception as exc:
        logger.debug("browser_escalation_failed url=%s error=%s", url, exc)
        return None