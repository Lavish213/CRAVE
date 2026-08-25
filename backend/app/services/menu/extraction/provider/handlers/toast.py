from __future__ import annotations

import logging
import re
from typing import List, Optional, Any

from app.services.menu.contracts import ExtractedMenuItem
from app.services.network.http_fetcher import fetch
from app.services.menu.extraction.js.js_menu_payload_adapter import convert_payload_to_menu_items
from app.services.menu.extraction.js.js_hydration_detector import detect_hydration_state


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# STRICT SLUG EXTRACTION
# ---------------------------------------------------------

def _extract_slug(url: str) -> Optional[str]:
    """
    Extract usable slug from Toast URL variants:
      /local/<slug>                  → slug
      /local/<slug>/r-<guid>         → slug (not guid)
      /online/<slug>                 → slug
      toasttab.com/<slug>            → slug (direct path)
    """
    try:
        # Strip query string and fragment
        clean = url.split("?")[0].split("#")[0].rstrip("/")
        parts = [p for p in clean.split("/") if p and p not in ("https:", "http:", "")]

        # Remove domain part
        domain_parts = []
        path_parts = []
        for p in parts:
            if "." in p:
                domain_parts.append(p)
            else:
                path_parts.append(p)

        if not path_parts:
            return None

        # /local/<slug>  or  /local/<slug>/r-<guid>
        if "local" in path_parts:
            idx = path_parts.index("local")
            if idx + 1 < len(path_parts):
                slug = path_parts[idx + 1]
                # Skip GUIDs (r-xxxxxxxx-...)
                if not slug.startswith("r-") or "-" not in slug[2:]:
                    return slug
                # If next is a GUID, slug is still the one after "local"
                return slug

        # /online/<slug>
        if "online" in path_parts:
            idx = path_parts.index("online")
            if idx + 1 < len(path_parts):
                return path_parts[idx + 1]

        # toasttab.com/<slug>/v3 or toasttab.com/<slug>/online
        for marker in ("v3", "online"):
            if marker in path_parts:
                idx = path_parts.index(marker)
                if idx > 0:
                    return path_parts[idx - 1]

        # Direct: toasttab.com/<slug>  (single path segment, not a GUID)
        if len(path_parts) == 1:
            candidate = path_parts[0]
            # Skip raw GUIDs
            if re.fullmatch(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", candidate):
                return None
            return candidate

        return None

    except Exception:
        return None


# ---------------------------------------------------------
# HARD FAIL LOGGER
# ---------------------------------------------------------

def _fail(reason: str, url: Optional[str]):
    logger.warning("toast_fail reason=%s url=%s", reason, url)
    return []


# ---------------------------------------------------------
# HYDRATION FALLBACK PARSER (extra safety)
# ---------------------------------------------------------

def _extract_embedded_json(html: str) -> List[Any]:
    payloads: List[Any] = []

    try:
        # crude but effective fallback (window.__APOLLO_STATE__ / etc.)
        matches = re.findall(r"window\.__.*?=\s*({.*?});", html, re.DOTALL)

        for m in matches:
            payloads.append(m)

    except Exception:
        pass

    return payloads


# ---------------------------------------------------------
# PLAYWRIGHT FALLBACK
# ---------------------------------------------------------

def _fetch_with_playwright(url: str) -> Optional[str]:
    """Render via headless Chromium to bypass CAPTCHA/thin-shell."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            # browser.close() must run even if page.content() (or context/
            # page creation) raises something other than PWTimeout -- see
            # browser_fallback.py's identical leak, confirmed live to
            # eventually OOM-kill the whole menu_enrichment worker.
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )
                page = context.new_page()
                try:
                    page.goto(url, timeout=15000)
                    page.wait_for_load_state("domcontentloaded", timeout=8000)
                    page.wait_for_timeout(2000)  # brief wait for Apollo state hydration
                except PWTimeout:
                    pass
                html = page.content()
            finally:
                browser.close()

        if html and len(html) > 1000:
            logger.debug("toast_playwright_ok url=%s len=%s", url, len(html))
            return html
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("toast_playwright_failed url=%s error=%s", url, exc)
    return None


# ---------------------------------------------------------
# HANDLER (FINAL)
# ---------------------------------------------------------

def handle_toast(
    html: str,
    url: Optional[str],
) -> List[ExtractedMenuItem]:

    if not url:
        return _fail("no_url", url)

    slug = _extract_slug(url)

    if not slug:
        return _fail("bad_slug", url)

    # 🔥 REAL ENTRY POINT (NOT FAKE API)
    page_url = f"https://order.toasttab.com/online/{slug}"

    try:
        response = fetch(
            page_url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/123.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
            },
        )

        if response.status_code != 200:
            return _fail(f"bad_status_{response.status_code}", url)

        html = response.text or ""

        # If CAPTCHA or thin shell, escalate to Playwright
        _is_captcha = "captcha" in html.lower() or "cf-challenge" in html.lower()
        _is_thin = len(html) < 2000 or "__APOLLO_STATE__" not in html
        if _is_captcha or _is_thin:
            pw_html = _fetch_with_playwright(page_url)
            if pw_html:
                html = pw_html

        if not html:
            return _fail("empty_html", url)

        # ---------------------------------------------------------
        # 1. PRIMARY: hydration detector
        # ---------------------------------------------------------

        try:
            hydration = detect_hydration_state(html)

            if isinstance(hydration, dict):
                raw = hydration.get("raw")

                if raw:
                    items = convert_payload_to_menu_items(raw)

                    if items:
                        logger.info("toast_success_hydration url=%s items=%s", url, len(items))
                        return items[:1500]

        except Exception as exc:
            logger.debug("toast_hydration_failed error=%s", exc)

        # ---------------------------------------------------------
        # 2. SECONDARY: embedded JSON scan
        # ---------------------------------------------------------

        payloads = _extract_embedded_json(html)

        for payload in payloads:
            try:
                items = convert_payload_to_menu_items(payload)

                if items:
                    logger.info("toast_success_embedded url=%s items=%s", url, len(items))
                    return items[:1500]

            except Exception:
                continue

        return _fail("no_items_found", url)

    except Exception as exc:
        return _fail(f"exception_{type(exc).__name__}", url)