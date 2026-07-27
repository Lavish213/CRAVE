"""
FetchStrategyRouter — Phase 4

Classifies a menu source URL into a fetch strategy BEFORE extraction runs.
Used by ExtractionController to decide how (or whether) to attempt a source.

Strategies:
    direct_request      Plain HTTPX — works for simple HTML/JSON endpoints.
    structured_request  HTTPX with API-mode headers — for known JSON APIs
                        (Toast menu API, ChowNow API, etc.).
    playwright_render   Headless Chromium — JS-rendered sites where HTML
                        is a thin shell (React, Next.js, Vue apps).
    authenticated_fetch Requires env-provided credentials (Grubhub cookies).
    fail_fast           Source is known-blocked or missing auth; skip without
                        wasting a network attempt.

Blocked reasons (logged, never silently swallowed):
    missing_auth        Credentials required and not present.
    captcha_domain      Domain is known to serve CAPTCHA on first hit.
    delivery_aggregator Third-party aggregator (DoorDash, UberEats) — no
                        public structured menu API.
    redirect_trap       Domain redirects to app store or login wall.
    dead_domain         DNS failure / domain not resolving.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


# =========================================================
# STRATEGY CONSTANTS
# =========================================================

STRATEGY_DIRECT = "direct_request"
STRATEGY_STRUCTURED = "structured_request"
STRATEGY_PLAYWRIGHT = "playwright_render"
STRATEGY_AUTH = "authenticated_fetch"
STRATEGY_FAIL_FAST = "fail_fast"

# =========================================================
# KNOWN DOMAIN PROFILES
# =========================================================

# Domains that reliably serve CAPTCHAs on first unauthenticated hit.
# Playwright MAY help but is expensive — mark for controlled escalation.
_CAPTCHA_DOMAINS = frozenset({
    "toasttab.com",
    "order.toasttab.com",
    "www.toasttab.com",
    "chownow.com",
    "ordering.chownow.com",
    "www.clover.com",
    "dashboard.clover.com",
    "squareup.com",
    # square.site uses direct API (not CAPTCHA) — removed
})

# Domains that require authenticated API calls (env creds).
_AUTH_REQUIRED_DOMAINS = frozenset({
    "grubhub.com",
    "www.grubhub.com",
    "api-gtm.grubhub.com",
})

# Delivery aggregators — public structured menu API doesn't exist.
_AGGREGATOR_DOMAINS = frozenset({
    "doordash.com",
    "ubereats.com",
    "postmates.com",
    "seamless.com",
    "caviar.com",
})

# Redirect traps — always send to app store or login.
_REDIRECT_TRAP_DOMAINS = frozenset({
    "yelp.com",
    "tripadvisor.com",
    "opentable.com",
    "resy.com",
    "tock.com",
})

# Known JSON API providers — use structured_request (API mode headers).
_API_PROVIDERS = frozenset({
    "toasttab.com",
    "order.toasttab.com",
    "api.chownow.com",
    "popmenu.com",
})


# =========================================================
# RESULT
# =========================================================

@dataclass(slots=True)
class FetchStrategyResult:
    url: str
    strategy: str                          # one of STRATEGY_* constants
    provider: Optional[str] = None         # "grubhub", "toast", "chownow", etc.
    blocked_reason: Optional[str] = None   # why strategy is fail_fast
    needs_auth: bool = False               # credentials required
    needs_browser: bool = False            # JS rendering required
    playwright_available: bool = False     # runtime check
    notes: list = field(default_factory=list)

    @property
    def should_skip(self) -> bool:
        return self.strategy == STRATEGY_FAIL_FAST


# =========================================================
# ROUTER
# =========================================================

class FetchStrategyRouter:
    """
    Classify a URL into a fetch strategy.

    Usage:
        router = FetchStrategyRouter()
        result = router.classify(url)
        if result.should_skip:
            log and continue
        else:
            run extraction with result.strategy
    """

    def __init__(self) -> None:
        self._playwright_available: Optional[bool] = None

    def classify(
        self,
        url: str,
        *,
        provider: Optional[str] = None,
    ) -> FetchStrategyResult:
        """
        Classify a single source URL.

        Args:
            url: The restaurant website or menu URL.
            provider: Optional already-detected provider slug.

        Returns:
            FetchStrategyResult describing how (or whether) to fetch.
        """
        host = self._host(url)
        apex = self._apex_domain(host)

        result = FetchStrategyResult(
            url=url,
            strategy=STRATEGY_DIRECT,
            provider=provider,
            playwright_available=self._check_playwright(),
        )

        # ── 1. Aggregator: no structured API, skip entirely ───────────
        if apex in _AGGREGATOR_DOMAINS:
            result.strategy = STRATEGY_FAIL_FAST
            result.blocked_reason = "delivery_aggregator"
            result.notes.append(f"{apex} has no public structured menu API")
            self._log(result)
            return result

        # ── 2. Redirect traps ─────────────────────────────────────────
        if apex in _REDIRECT_TRAP_DOMAINS:
            result.strategy = STRATEGY_FAIL_FAST
            result.blocked_reason = "redirect_trap"
            result.notes.append(f"{apex} always redirects away from menu content")
            self._log(result)
            return result

        # ── 3. Auth-required (Grubhub) ────────────────────────────────
        if apex in _AUTH_REQUIRED_DOMAINS:
            result.provider = result.provider or "grubhub"
            result.needs_auth = True
            if not self._grubhub_creds_present():
                result.strategy = STRATEGY_FAIL_FAST
                result.blocked_reason = "missing_auth"
                result.notes.append(
                    "GRUBHUB_COOKIES env var not set — "
                    "run scripts/grab_grubhub_cookies.py to obtain"
                )
                self._log(result)
                return result
            result.strategy = STRATEGY_AUTH
            self._log(result)
            return result

        # ── 4. Known CAPTCHA domains — try browser if available ───────
        if apex in _CAPTCHA_DOMAINS or host in _CAPTCHA_DOMAINS:
            result.needs_browser = True
            if result.playwright_available:
                result.strategy = STRATEGY_PLAYWRIGHT
                result.notes.append(
                    f"{apex} is known CAPTCHA domain — using Playwright"
                )
            else:
                # Playwright not available: attempt structured API path
                # (toast_extractor uses API endpoints that bypass HTML fetch)
                if apex in _API_PROVIDERS or host in _API_PROVIDERS:
                    result.strategy = STRATEGY_STRUCTURED
                    result.notes.append(
                        f"{apex} CAPTCHA domain but has JSON API path — trying structured"
                    )
                else:
                    result.strategy = STRATEGY_FAIL_FAST
                    result.blocked_reason = "captcha_domain"
                    result.notes.append(
                        f"{apex} is CAPTCHA-protected and Playwright not available. "
                        "Install playwright: python -m playwright install chromium"
                    )
                    self._log(result)
                    return result
            self._log(result)
            return result

        # ── 5. Known API providers (non-CAPTCHA) ─────────────────────
        if apex in _API_PROVIDERS or host in _API_PROVIDERS:
            result.strategy = STRATEGY_STRUCTURED
            self._log(result)
            return result

        # ── 6. Default: direct HTTP + optional Playwright escalation ──
        result.strategy = STRATEGY_DIRECT
        if result.playwright_available:
            result.notes.append("Playwright available for escalation if needed")
        self._log(result)
        return result

    def classify_batch(
        self,
        urls: list[str],
        *,
        provider: Optional[str] = None,
    ) -> dict[str, FetchStrategyResult]:
        """Classify multiple URLs at once."""
        return {url: self.classify(url, provider=provider) for url in urls}

    # =========================================================
    # INTERNAL
    # =========================================================

    def _check_playwright(self) -> bool:
        if self._playwright_available is None:
            try:
                import playwright  # noqa: F401
                self._playwright_available = True
            except ImportError:
                self._playwright_available = False
        return self._playwright_available  # type: ignore[return-value]

    @staticmethod
    def _grubhub_creds_present() -> bool:
        return bool(os.environ.get("GRUBHUB_COOKIES", "").strip())

    @staticmethod
    def _host(url: str) -> str:
        try:
            h = urlparse(url).netloc.lower()
            return h.lstrip("www.") if h.startswith("www.") else h
        except Exception:
            return ""

    @staticmethod
    def _apex_domain(host: str) -> str:
        """Return last two domain parts: sub.example.com → example.com"""
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host

    @staticmethod
    def _log(result: FetchStrategyResult) -> None:
        if result.strategy == STRATEGY_FAIL_FAST:
            logger.info(
                "fetch_strategy url=%s strategy=fail_fast blocked_reason=%s needs_auth=%s needs_browser=%s",
                result.url,
                result.blocked_reason,
                result.needs_auth,
                result.needs_browser,
            )
        else:
            logger.debug(
                "fetch_strategy url=%s strategy=%s provider=%s needs_auth=%s needs_browser=%s",
                result.url,
                result.strategy,
                result.provider,
                result.needs_auth,
                result.needs_browser,
            )


# =========================================================
# MODULE-LEVEL SINGLETON
# =========================================================

_router = FetchStrategyRouter()


def classify_fetch_strategy(
    url: str,
    *,
    provider: Optional[str] = None,
) -> FetchStrategyResult:
    """Convenience function using module-level router instance."""
    return _router.classify(url, provider=provider)
