from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from app.services.network.http_fetcher import fetch
from app.services.menu.discovery.provider_discovery import discover_provider_urls


logger = logging.getLogger(__name__)


_PROVIDER_DOMAINS: dict[str, str] = {
    # Direct menu API providers — delivery platforms (doordash, ubereats, grubhub)
    # are intentionally excluded; they have dedicated ingest pipelines.
    "toasttab.com": "toast",
    "square.site": "square",
    "squareup.com": "square",
    "clover.com": "clover",
    "popmenu.com": "popmenu",
    "chownow.com": "chownow",
    "olo.com": "olo",
}

_PROBE_PATHS = [
    "",           # probe the homepage first
    "/menu",
    "/order",
    "/order-online",
    "/online-ordering",
    "/food-menu",
]

_SKIP_DOMAINS = frozenset({
    "yelp.com",
    "tripadvisor.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
})

_JSONLD_MENU_RE = re.compile(
    r'"@type"\s*:\s*"(?:Menu|MenuSection|MenuItem)"',
    re.IGNORECASE,
)

MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class ProbeResult:
    menu_source_url: Optional[str]
    provider: Optional[str]
    confidence: float

    @property
    def found(self) -> bool:
        return self.menu_source_url is not None and self.confidence >= MIN_CONFIDENCE


def _provider_from_url(url: str) -> Optional[str]:
    """Return provider name if the URL contains a known provider domain."""
    lower = url.lower()
    for domain, provider in _PROVIDER_DOMAINS.items():
        if domain in lower:
            return provider
    return None


def _should_skip(website: str) -> bool:
    """Return True for aggregator and social domains that are never menu sources."""
    try:
        netloc = urlparse(website).netloc.lower().removeprefix("www.")
        return any(netloc == d or netloc.endswith("." + d) for d in _SKIP_DOMAINS)
    except Exception:
        return False


def _normalize_website(website: str) -> str:
    """Ensure the website string has an https:// scheme and no trailing slash."""
    website = website.strip()
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    return website.rstrip("/")


def probe_website(website: str) -> ProbeResult:
    """
    Probe a restaurant website to find its menu provider URL.

    Strategy (ordered by confidence):
      1. Fetch each candidate path. If the final URL (after redirect) is a
         known provider domain → confidence 1.0, return immediately.
      2. Scan HTML for provider-domain hrefs/iframes/scripts → confidence 0.9.
         Continue scanning paths in case a later path yields a 1.0 redirect.
      3. Detect JSON-LD Menu schema in HTML → confidence 0.7.

    Only returns a result with .found=True when confidence >= 0.7.
    Idempotent — no DB writes, no side effects.
    """
    website = _normalize_website(website)

    if not website or _should_skip(website):
        return ProbeResult(menu_source_url=None, provider=None, confidence=0.0)

    best = ProbeResult(menu_source_url=None, provider=None, confidence=0.0)

    for path in _PROBE_PATHS:
        url = website + path

        try:
            res = fetch(url, mode="document")
        except Exception as exc:
            logger.debug("probe_fetch_failed url=%s err=%s", url, exc)
            continue

        if res.status_code not in (200, 301, 302, 303, 307, 308):
            continue

        # Check 1: did the final URL (after redirects) land on a provider?
        final_url = str(res.url)
        provider = _provider_from_url(final_url)
        if provider:
            logger.info(
                "probe_redirect_hit url=%s provider=%s final=%s",
                url, provider, final_url,
            )
            return ProbeResult(
                menu_source_url=final_url,
                provider=provider,
                confidence=1.0,
            )

        # Check 2: does the HTML reference a provider domain?
        try:
            html = res.text or ""
        except Exception:
            continue

        if not html:
            continue

        provider_urls = discover_provider_urls(html)
        if provider_urls:
            provider_url = provider_urls[0]
            prov = _provider_from_url(provider_url)
            if prov:
                candidate = ProbeResult(
                    menu_source_url=provider_url,
                    provider=prov,
                    confidence=0.9,
                )
                if candidate.confidence > best.confidence:
                    best = candidate
                continue  # keep scanning paths only when we got a real 0.9 hit

        # Check 3: JSON-LD Menu schema in HTML?
        if _JSONLD_MENU_RE.search(html):
            candidate = ProbeResult(
                menu_source_url=url,
                provider="jsonld",
                confidence=0.7,
            )
            if candidate.confidence > best.confidence:
                best = candidate

    logger.info(
        "probe_done website=%s provider=%s confidence=%.2f",
        website, best.provider, best.confidence,
    )
    return best
