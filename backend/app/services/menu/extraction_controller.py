"""
ExtractionController — Phase B

Decides WHICH extractor runs per place and executes it.

Priority:
    1. Toast      (toasttab.com)
    2. ChowNow    (chownow.com)
    3. Popmenu    (popmenu.com)
    4. Clover     (clover.com)
    5. Square     (squareup.com)
    6. Website structured  (JSON-LD, hydration)
    7. Website HTML        (heuristic + Playwright escalation)
    8. Google              (fallback only, marks fallback_used=True)

Behavior:
    - classify fetch strategy BEFORE attempting extraction
    - skip sources that are fail_fast (no credentials, known aggregators)
    - run highest-priority extractor
    - if fails → fallback down the chain
    - stop when menu items are produced
    - returns ExtractionControllerResult with full lineage

Rules:
    - NEVER writes fake data
    - NEVER bypasses Phase 3 for images
    - Google only used when everything else fails
    - Extraction failures separated from access failures in logs
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.provider.provider_detector import detect_provider
from app.services.menu.extraction.js.js_provider_router import route_provider
from app.services.menu.extraction.html_menu_extractor import extract_html_menu
from app.services.menu.extraction.fetch_html import fetch_html
from app.services.menu.fetch.fetch_strategy_router import (
    FetchStrategyResult,
    classify_fetch_strategy,
    STRATEGY_FAIL_FAST,
    STRATEGY_PLAYWRIGHT,
    STRATEGY_AUTH,
    STRATEGY_STRUCTURED,
    STRATEGY_DIRECT,
)


# =========================================================
# FAILURE TYPE CONSTANTS
# =========================================================

FAILURE_MISSING_AUTH      = "missing_auth"
FAILURE_CAPTCHA_BLOCK     = "captcha_block"
FAILURE_CLOUDFLARE_BLOCK  = "cloudflare_block"
FAILURE_JS_SHELL          = "js_shell"
FAILURE_PARSER_MISS       = "parser_miss"
FAILURE_DEAD_SITE         = "dead_site"
FAILURE_REDIRECT_TRAP     = "redirect_trap"
FAILURE_FETCH_TIMEOUT     = "fetch_timeout"
FAILURE_PROVIDER_BUG      = "provider_bug"
FAILURE_BLOCKED_PROVIDER  = "blocked_provider"
FAILURE_SUCCESS_ZERO_ITEMS = "success_zero_items"


def _classify_fetch_error(exc: Exception) -> str:
    """Map a fetch exception to a typed failure reason."""
    msg = str(exc).lower()
    if "nodename nor servname" in msg or "name or service not known" in msg or "dns" in msg:
        return FAILURE_DEAD_SITE
    if "timeout" in msg:
        return FAILURE_FETCH_TIMEOUT
    if "captcha" in msg:
        return FAILURE_CAPTCHA_BLOCK
    if "cloudflare" in msg or "cf-challenge" in msg:
        return FAILURE_CLOUDFLARE_BLOCK
    if "403" in msg or "forbidden" in msg:
        return FAILURE_BLOCKED_PROVIDER
    if "redirect" in msg:
        return FAILURE_REDIRECT_TRAP
    if "empty" in msg or "blocked" in msg:
        return FAILURE_CAPTCHA_BLOCK
    return FAILURE_DEAD_SITE


logger = logging.getLogger(__name__)


# =========================================================
# RESULT CONTRACT
# =========================================================

@dataclass(slots=True)
class ExtractionControllerResult:
    place_id: str
    items: List[ExtractedMenuItem] = field(default_factory=list)
    provider: Optional[str] = None
    method: str = "none"
    fallback_used: bool = False
    google_used: bool = False
    error: Optional[str] = None

    # Access diagnostics
    strategy_used: Optional[str] = None
    blocked_reason: Optional[str] = None
    needs_auth: bool = False
    needs_browser: bool = False
    access_failure: bool = False    # True = fetch failed (not extraction logic)
    extraction_failure: bool = False  # True = fetch ok but items=0

    # Typed failure reason (one of FAILURE_* constants)
    failure_reason: Optional[str] = None

    # URL that actually yielded items (may differ from place.website)
    selected_url: Optional[str] = None

    @property
    def success(self) -> bool:
        return len(self.items) >= 2

    @property
    def item_count(self) -> int:
        return len(self.items)


# =========================================================
# CONTROLLER
# =========================================================

class ExtractionController:
    """
    Routes extraction for a single place through the priority chain.

    Usage:
        controller = ExtractionController()
        result = controller.extract_for_place(place)
    """

    MIN_ITEMS = 2

    def extract_for_place(self, place) -> ExtractionControllerResult:
        place_id = str(getattr(place, "id", "") or "")
        website = str(getattr(place, "website", "") or "").strip()

        # Prefer menu_source_url (verified provider URL from discovery) over website
        menu_source_url = str(getattr(place, "menu_source_url", "") or "").strip()
        website = menu_source_url or website

        result = ExtractionControllerResult(place_id=place_id)

        if not place_id:
            result.error = "missing_place_id"
            return result

        logger.info(
            "extraction_controller.start place_id=%s website=%s menu_source_url=%s",
            place_id, website, bool(menu_source_url),
        )

        if not website:
            result.error = "no_website"
            return result

        # ── Pre-flight: classify fetch strategy ───────────────────────
        strategy = classify_fetch_strategy(website)
        result.strategy_used = strategy.strategy
        result.needs_auth = strategy.needs_auth
        result.needs_browser = strategy.needs_browser

        if strategy.notes:
            logger.info(
                "extraction_controller.strategy_notes place_id=%s %s",
                place_id,
                " | ".join(strategy.notes),
            )

        # ── Fail-fast: known blocked sources ─────────────────────────
        if strategy.strategy == STRATEGY_FAIL_FAST:
            result.error = strategy.blocked_reason or "fail_fast"
            result.blocked_reason = strategy.blocked_reason
            result.access_failure = True
            # Map strategy blocked_reason to typed failure
            _reason_map = {
                "missing_auth": FAILURE_MISSING_AUTH,
                "captcha_domain": FAILURE_CAPTCHA_BLOCK,
                "delivery_aggregator": FAILURE_BLOCKED_PROVIDER,
                "redirect_trap": FAILURE_REDIRECT_TRAP,
                "dead_domain": FAILURE_DEAD_SITE,
            }
            result.failure_reason = _reason_map.get(
                strategy.blocked_reason or "", FAILURE_BLOCKED_PROVIDER
            )
            logger.info(
                "extraction_controller.fail_fast place_id=%s blocked_reason=%s failure_reason=%s",
                place_id,
                strategy.blocked_reason,
                result.failure_reason,
            )
            return result

        # ── STAGE 1: Provider detection ───────────────────────────────
        provider = detect_provider("", website)
        logger.info(
            "extraction_controller.provider_detected place_id=%s provider=%s strategy=%s",
            place_id,
            provider,
            strategy.strategy,
        )

        if provider and provider not in ("google", "doordash", "ubereats"):
            items, pfail = self._try_provider(
                website=website,
                provider=provider,
                strategy=strategy,
            )

            if self._valid(items):
                result.items = items
                result.provider = provider
                result.method = "provider_direct"
                result.strategy_used = strategy.strategy
                result.selected_url = website
                logger.info(
                    "extraction_controller.provider_success place_id=%s provider=%s items=%s strategy=%s",
                    place_id, provider, len(items), strategy.strategy,
                )
                return result

            if pfail:
                result.failure_reason = pfail

            logger.info(
                "extraction_controller.provider_failed place_id=%s provider=%s strategy=%s failure=%s",
                place_id, provider, strategy.strategy, pfail,
            )

        # ── STAGE 2: HTML structured (JSON-LD) ───────────────────────
        items, sfail = self._try_html_structured(website=website)

        if self._valid(items):
            result.items = items
            result.method = "html_structured"
            result.fallback_used = True
            result.selected_url = website
            logger.info(
                "extraction_controller.html_structured_success place_id=%s items=%s",
                place_id, len(items),
            )
            return result

        # ── STAGE 3: HTML heuristic + menu discovery + optional Playwright
        items, hfail, selected_url = self._try_html_heuristic(
            website=website, strategy=strategy
        )

        if self._valid(items):
            result.items = items
            result.method = (
                "html_playwright" if strategy.playwright_available and strategy.needs_browser
                else "html_heuristic"
            )
            result.fallback_used = True
            result.selected_url = selected_url or website
            logger.info(
                "extraction_controller.html_heuristic_success place_id=%s items=%s method=%s url=%s",
                place_id, len(items), result.method, result.selected_url,
            )
            return result

        # ── STAGE 4: Google fallback (stub) ───────────────────────────
        items = self._try_google(place)

        if self._valid(items):
            result.items = items
            result.method = "google_fallback"
            result.fallback_used = True
            result.google_used = True
            result.selected_url = website
            return result

        # All stages failed — pick most specific failure_reason seen
        result.error = "all_extractors_failed"
        result.extraction_failure = True
        # Use most specific failure seen across stages
        if not result.failure_reason:
            result.failure_reason = hfail or sfail or pfail or FAILURE_PARSER_MISS
        logger.info(
            "extraction_controller.all_failed place_id=%s strategy=%s provider=%s failure_reason=%s",
            place_id, strategy.strategy, provider, result.failure_reason,
        )
        return result

    # =========================================================
    # STAGE IMPLEMENTATIONS
    # =========================================================

    def _try_provider(
        self,
        *,
        website: str,
        provider: str,
        strategy: FetchStrategyResult,
    ):
        """
        Run detected provider handler.
        Returns (items, failure_reason).
        """
        try:
            # First: URL-only (no HTML fetch needed for API-based providers)
            items = route_provider("", website)
            if self._valid(items):
                return items, None

            # Second: fetch HTML and retry (needed for hydration-based providers)
            if strategy.strategy == STRATEGY_FAIL_FAST:
                return [], FAILURE_BLOCKED_PROVIDER

            html = None
            try:
                # Use Playwright when the provider is known CAPTCHA/JS-heavy
                if strategy.needs_browser and strategy.playwright_available:
                    html = self._fetch_with_playwright(website)
                if not html:
                    html = fetch_html(website)
            except Exception as exc:
                failure = _classify_fetch_error(exc)
                logger.debug(
                    "extraction_controller.provider_html_fetch_failed "
                    "provider=%s error=%s failure=%s",
                    provider, exc, failure,
                )
                return [], failure

            if html:
                items = route_provider(html, website)

            if self._valid(items):
                return items, None

            # Provider-specific blocks (e.g. Toast Apollo state null)
            if provider in ("toast", "chownow", "clover", "square", "popmenu"):
                return [], FAILURE_BLOCKED_PROVIDER

            return [], FAILURE_PARSER_MISS

        except Exception as exc:
            logger.debug(
                "extraction_controller.provider_exception provider=%s error=%s",
                provider, exc,
            )
            return [], FAILURE_PROVIDER_BUG

    def _try_html_structured(self, *, website: str):
        """
        JSON-LD / schema.org structured data.
        Returns (items, failure_reason).
        """
        try:
            from app.services.menu.extraction.jsonld_menu_extractor import extract_jsonld_menu

            try:
                html = fetch_html(website)
            except Exception as exc:
                return [], _classify_fetch_error(exc)

            if not html:
                return [], FAILURE_PARSER_MISS

            items = extract_jsonld_menu(html, source_url=website)

            # If JSON-LD has hasMenu URL, follow it
            if not items:
                import json
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string or "")
                        menu_url = self._extract_has_menu_url(data)
                        if menu_url and menu_url != website:
                            try:
                                menu_html = fetch_html(menu_url)
                            except Exception:
                                continue
                            if menu_html:
                                items = extract_jsonld_menu(menu_html, source_url=menu_url)
                                if items:
                                    break
                    except Exception:
                        continue

            return items or [], FAILURE_PARSER_MISS

        except Exception as exc:
            logger.debug("extraction_controller.html_structured_failed error=%s", exc)
            return [], FAILURE_PARSER_MISS

    def _extract_has_menu_url(self, data) -> Optional[str]:
        """Extract hasMenu URL from JSON-LD data if it's a string URL."""
        if isinstance(data, dict):
            has_menu = data.get("hasMenu")
            if isinstance(has_menu, str) and has_menu.startswith("http"):
                return has_menu
            # Check @graph
            for item in data.get("@graph", []):
                url = self._extract_has_menu_url(item)
                if url:
                    return url
        return None

    def _try_html_heuristic(
        self,
        *,
        website: str,
        strategy: FetchStrategyResult,
    ):
        """
        HTML heuristic extraction with menu page discovery.
        Tries homepage first, then /menu, /menus, nav links, hasMenu.
        Returns (items, failure_reason, selected_url).
        """
        homepage_html: Optional[str] = None
        last_failure: str = FAILURE_PARSER_MISS
        is_thin_shell: bool = False

        # ── Step 1: fetch homepage ────────────────────────────────────
        try:
            homepage_html = fetch_html(website)
        except Exception as exc:
            last_failure = _classify_fetch_error(exc)
            logger.debug(
                "extraction_controller.homepage_fetch_failed url=%s failure=%s error=%s",
                website, last_failure, exc,
            )
            # Can't even fetch homepage — skip menu discovery
            return [], last_failure, None

        # ── Step 2: thin-shell detection + optional Playwright ────────
        is_thin_shell = self._is_thin_shell(homepage_html or "")

        if is_thin_shell and strategy.playwright_available:
            logger.info("extraction_controller.playwright_escalate url=%s", website)
            rendered = self._fetch_with_playwright(website)
            if rendered:
                homepage_html = rendered
                is_thin_shell = False

        # ── Step 3: try extraction on homepage ────────────────────────
        if homepage_html:
            items = extract_html_menu(homepage_html, source_url=website) or []
            if self._valid(items):
                return items, None, website

        # ── Step 4: menu page discovery ───────────────────────────────
        menu_candidates = self._discover_menu_pages(website, homepage_html or "")

        for candidate_url in menu_candidates:
            try:
                menu_html = fetch_html(candidate_url)
            except Exception as exc:
                logger.debug(
                    "extraction_controller.menu_page_fetch_failed url=%s error=%s",
                    candidate_url, exc,
                )
                continue

            if not menu_html:
                continue

            candidate_is_thin = self._is_thin_shell(menu_html)
            if candidate_is_thin and strategy.playwright_available:
                rendered = self._fetch_with_playwright(candidate_url)
                if rendered:
                    menu_html = rendered

            items = extract_html_menu(menu_html, source_url=candidate_url) or []

            if self._valid(items):
                logger.info(
                    "extraction_controller.menu_page_success place_url=%s selected=%s items=%s",
                    website, candidate_url, len(items),
                )
                return items, None, candidate_url

        # ── Nothing worked ────────────────────────────────────────────
        if is_thin_shell:
            last_failure = FAILURE_JS_SHELL

        return [], last_failure, None

    def _discover_menu_pages(self, website: str, homepage_html: str) -> List[str]:
        """
        Discover menu-specific pages before extraction.
        Priority:
            1. Common paths (/menu, /menus, /our-menu, /order)
            2. Nav links from homepage HTML (menu_discovery_engine)
            3. schema.org hasMenu (handled separately in _try_html_structured)
        Returns deduplicated list of candidate URLs (best first).
        """
        from urllib.parse import urljoin
        from app.services.menu.discovery.menu_discovery_engine import find_menu_links

        seen: set = {website.rstrip("/")}
        candidates: List[str] = []

        # 1. Common menu paths (highest priority)
        for path in ("/menu", "/menus", "/our-menu", "/food-menu", "/menu.html",
                     "/order", "/order-online", "/dining", "/eat"):
            url = urljoin(website, path)
            norm = url.rstrip("/")
            if norm not in seen:
                seen.add(norm)
                candidates.append(url)

        # 2. Nav links discovered from homepage
        if homepage_html:
            try:
                nav_links = find_menu_links(homepage_html, website, max_links=10)
                for link in nav_links:
                    norm = link.rstrip("/")
                    if norm not in seen:
                        seen.add(norm)
                        candidates.append(link)
            except Exception as exc:
                logger.debug("extraction_controller.discovery_failed error=%s", exc)

        return candidates[:8]

    def _try_google(self, place) -> List[ExtractedMenuItem]:
        """Google fallback — placeholder."""
        return []

    # =========================================================
    # PLAYWRIGHT ESCALATION
    # =========================================================

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """
        Fetch URL via headless Chromium, wait for JS to render menu content.
        Returns rendered HTML or None on failure.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )
                # browser.close() must run even if page.content() (or
                # context/page creation) raises something other than
                # PWTimeout -- see browser_fallback.py's identical leak,
                # confirmed live to eventually OOM-kill the whole
                # menu_enrichment worker.
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
                        page.goto(url, timeout=20000)
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                        # Small wait for async menu renders
                        page.wait_for_timeout(2000)
                    except PWTimeout:
                        pass  # take whatever loaded

                    html = page.content()
                finally:
                    browser.close()

            if html and len(html) > 500:
                logger.debug("playwright_fetch_ok url=%s len=%s", url, len(html))
                return html

        except ImportError:
            pass
        except Exception as exc:
            logger.debug("playwright_fetch_failed url=%s error=%s", url, exc)

        return None

    # =========================================================
    # HELPERS
    # =========================================================

    def _is_thin_shell(self, html: str) -> bool:
        """
        Returns True if HTML is a JS-only thin shell with no real menu content.
        Heuristics: tiny visible text, no price patterns, Next.js/React bootstrap.
        """
        if not html or len(html) < 200:
            return True

        import re
        lower = html.lower()

        # JS framework bootstrap markers
        js_markers = (
            "_next/static",
            "__next_data__",
            "react-root",
            "ng-version",
            "__vue__",
            "window.__remixcontext",
        )
        has_js_marker = any(m in lower for m in js_markers)

        # Price pattern — if present, probably not thin
        has_price = bool(re.search(r"\$\s*\d+(?:\.\d{2})?", html))

        # Minimal visible text (strip tags, check length)
        text_only = re.sub(r"<[^>]+>", " ", html)
        visible_len = len(text_only.split())

        return has_js_marker and not has_price and visible_len < 200

    def _valid(self, items: Optional[List]) -> bool:
        return bool(items) and len(items) >= self.MIN_ITEMS
