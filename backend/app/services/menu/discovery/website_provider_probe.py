from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

from app.services.network.http_fetcher import fetch
from app.services.menu.discovery.provider_discovery import discover_provider_urls


logger = logging.getLogger(__name__)


# ── Scoring ───────────────────────────────────────────────────────────────────

_PROVIDER_SCORES: dict[str, int] = {
    "toasttab.com":  100,
    "popmenu.com":    90,
    "square.site":    80,
    "squareup.com":   80,
    "chownow.com":    70,
    "olo.com":        60,
}

_MENU_PATH_SCORE = 40  # fallback: /menu page only, no provider

# ── Hard block — never save these ────────────────────────────────────────────

_HARD_BLOCK: frozenset[str] = frozenset({
    "grubhub.com",
    "ubereats.com",
    "doordash.com",
    "yelp.com",
    "seamless.com",
    "tripadvisor.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "clover.com",     # provider homepage — no restaurant-specific path available
    "cloversites.com",
})

# ── Probe paths ───────────────────────────────────────────────────────────────
# Phase 2B: Full path list as specified.

_PROBE_PATHS = [
    "",
    "/menu",
    "/order",
    "/order-online",
    "/online-order",
    "/food",
    "/eat",
    "/online-ordering",
    "/food-menu",
]

# ── JSON-LD detection ─────────────────────────────────────────────────────────

_JSONLD_MENU_RE = re.compile(
    r'"@type"\s*:\s*"(?:Menu|MenuSection|MenuItem)"',
    re.IGNORECASE,
)

# ── Quality threshold ─────────────────────────────────────────────────────────

MIN_SCORE = 40  # must be at least a valid /menu page


@dataclass(frozen=True)
class ProbeResult:
    menu_source_url: Optional[str]
    provider: Optional[str]
    score: int          # 0–100
    confidence: float   # backward-compat alias: score / 100

    @property
    def found(self) -> bool:
        return self.menu_source_url is not None and self.score >= MIN_SCORE


def _NOT_FOUND() -> ProbeResult:
    return ProbeResult(menu_source_url=None, provider=None, score=0, confidence=0.0)


# ── URL helpers ───────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Force https, strip query params and fragments, remove trailing slash."""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    normalized = parsed._replace(
        scheme="https",
        query="",
        fragment="",
        path=parsed.path.rstrip("/") or "/",
    )
    result = urlunparse(normalized)
    return result.rstrip("/")


def _is_hard_blocked(url: str) -> bool:
    """True if URL matches a hard-blocked domain."""
    try:
        netloc = urlparse(url).netloc.lower().removeprefix("www.")
        return any(netloc == d or netloc.endswith("." + d) for d in _HARD_BLOCK)
    except Exception:
        return False


def _score_url(url: str) -> tuple[int, str | None]:
    """
    Return (score, provider_name) for a URL.
    Returns (0, None) if hard-blocked or fails quality checks.
    """
    if not url or _is_hard_blocked(url):
        return 0, None

    lower = url.lower()

    for domain, score in _PROVIDER_SCORES.items():
        if domain not in lower:
            continue

        # Quality checks per provider
        if domain == "toasttab.com":
            # Accept: /online, /v3, UUID, /r/ (restaurant slug), or any non-root path
            # Reject only toasttab.com homepage and generic marketing pages
            path = urlparse(url).path.rstrip("/")
            if path in ("", "/about", "/pricing", "/demo", "/restaurants", "/partners"):
                return 0, None
            return score, "toast"

        if domain == "squareup.com":
            # Must have /store/ path — squareup.com homepage = blocked
            if "/store/" not in lower:
                return 0, None
            return score, "square"

        if domain == "square.site":
            # Restaurant-specific subdomain — always valid
            return score, "square"

        if domain == "popmenu.com":
            # Must not be popmenu.com homepage or marketing page
            path = urlparse(url).path
            if path in ("", "/", "/about", "/pricing", "/demo"):
                return 0, None
            return score, "popmenu"

        if domain == "chownow.com":
            return score, "chownow"

        if domain == "olo.com":
            return score, "olo"

    return 0, None


def _normalize_website(website: str) -> str:
    url = website.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


# ── Main probe ────────────────────────────────────────────────────────────────

def probe_website(website: str) -> ProbeResult:
    """
    Probe a restaurant website to find its best menu provider URL.

    Strategy:
      0. Fast path: if website itself IS a provider URL → return immediately (no HTTP).
      1. Fetch each candidate path.
         a. Check if final URL (after redirect) is a known provider → score by provider.
         b. Scan HTML for provider links/iframes/scripts → score each, keep best.
         c. Check for JSON-LD Menu schema → score=40 (menu page only).
      2. Score ALL candidates. Select highest score only.
      3. Apply quality filters (reject provider homepages, aggregators).
      4. Normalize selected URL (https, strip params, no trailing slash).

    Hard blocks: grubhub, ubereats, doordash, yelp, seamless, clover.com homepage.
    Returns ProbeResult with .found=False if nothing valid found.
    """
    website = _normalize_website(website)

    if not website or _is_hard_blocked(website):
        return _NOT_FOUND()

    # ── Fast path: website IS already a provider URL — skip all HTTP ──────────
    direct_norm = _normalize_url(website)
    direct_score, direct_provider = _score_url(direct_norm)
    if direct_score >= MIN_SCORE:
        logger.info(
            "probe_fast_path website=%s provider=%s score=%s",
            website, direct_provider, direct_score,
        )
        return ProbeResult(
            menu_source_url=direct_norm,
            provider=direct_provider,
            score=direct_score,
            confidence=direct_score / 100.0,
        )

    best_score = 0
    best_url: str | None = None
    best_provider: str | None = None
    consecutive_failures = 0

    for path in _PROBE_PATHS:
        url = website + path

        try:
            res = fetch(url, mode="document")
            consecutive_failures = 0
        except Exception as exc:
            msg = str(exc).lower()
            logger.debug("probe_fetch_err url=%s error=%s", url, exc)
            # Dead domain (DNS failure) — no point probing further paths
            if "nodename nor servname" in msg or "name or service not known" in msg:
                logger.debug("probe_dns_dead url=%s — stopping", url)
                break
            consecutive_failures += 1
            if consecutive_failures >= 3:
                logger.debug("probe_too_many_errors website=%s — stopping", website)
                break  # domain is dead or blocking — stop
            continue

        # 404/410 = path doesn't exist (normal for subpaths) — skip but don't count as fatal
        if res.status_code in (404, 410):
            logger.debug("probe_path_not_found status=%s url=%s", res.status_code, url)
            continue

        if res.status_code not in (200, 301, 302, 303, 307, 308):
            logger.debug("probe_bad_status status=%s url=%s", res.status_code, url)
            consecutive_failures += 1
            if consecutive_failures >= 3:
                break
            continue

        # ── Check 1: redirect destination ────────────────────────────────────
        final_url = _normalize_url(str(res.url))
        score, provider = _score_url(final_url)
        logger.debug(
            "probe_path path=%s final_url=%s score=%s provider=%s",
            path or "/", final_url[:80], score, provider,
        )

        if score > best_score:
            best_score = score
            best_url = final_url
            best_provider = provider

        # Early stop only when highest possible score reached (can't improve further)
        _max_possible = max(_PROVIDER_SCORES.values())
        if best_score >= _max_possible:
            logger.debug("probe_early_stop_max provider=%s score=%s", best_provider, best_score)
            break

        # ── Check 2: links in HTML ────────────────────────────────────────────
        try:
            html = res.text or ""
        except Exception:
            continue

        if not html:
            continue

        provider_links = discover_provider_urls(html)
        if provider_links:
            logger.debug("probe_html_links count=%s sample=%s", len(provider_links), provider_links[:3])

        for candidate_url in provider_links:
            norm = _normalize_url(candidate_url)
            s, p = _score_url(norm)
            if s > best_score:
                best_score = s
                best_url = norm
                best_provider = p
                logger.debug("probe_html_link_better url=%s score=%s provider=%s", norm[:80], s, p)

        # Same early-stop check after HTML link scan
        if best_score >= _max_possible:
            logger.debug("probe_early_stop_max_html provider=%s score=%s", best_provider, best_score)
            break

        # ── Check 3: JSON-LD Menu fallback ────────────────────────────────────
        # Fire on any path (/, /menu, /order, etc.) — not just /menu
        if best_score == 0 and _JSONLD_MENU_RE.search(html):
            best_score = _MENU_PATH_SCORE
            best_url = _normalize_url(url)
            best_provider = "jsonld"
            logger.debug("probe_jsonld_match url=%s", best_url[:80])

    if best_score < MIN_SCORE or not best_url:
        logger.debug("probe_no_result website=%s best_score=%s", website, best_score)
        return _NOT_FOUND()

    logger.info(
        "probe_found website=%s provider=%s score=%s url=%s",
        website, best_provider, best_score, best_url,
    )
    return ProbeResult(
        menu_source_url=best_url,
        provider=best_provider,
        score=best_score,
        confidence=best_score / 100.0,
    )
