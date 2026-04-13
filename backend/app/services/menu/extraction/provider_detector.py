from __future__ import annotations

import re
from typing import Optional, Dict
from urllib.parse import urlparse


_PROVIDER_PATTERNS: Dict[str, list[str]] = {
    "toast": ["toasttab.com", "toastcdn", "toast-menu", "toast-order"],
    "square": ["squareup.com", "square.site", "squarecdn", "square-online"],
    "clover": ["clover.com", "clovercdn"],
    "popmenu": ["popmenu.com", "popmenucdn"],
    "chownow": ["chownow.com", "ordering.chownow.com"],
    "olo": ["olo.com", "olo-ordering"],
    "spoton": ["spoton.com", "spotonordering"],
    "menufy": ["menufy.com"],
    "bentobox": ["bentoboxcdn.com", "getbento.com"],
    "lunchbox": ["lunchbox.io"],
    "gloriafood": ["gloriafood.com"],
    "orderonline": ["order.online"],
    "upserve": ["upserve.com", "upservecdn"],
}


_DELIVERY_PATTERNS = (
    "doordash.com",
    "ubereats.com",
    "grubhub.com",
    "postmates.com",
)


_SCRIPT_PROVIDER_REGEX = {
    "toast": re.compile(r"\btoast(tab|cdn|order)\b", re.I),
    "square": re.compile(r"\bsquare(up|\.site|online)\b", re.I),
    "clover": re.compile(r"\bclover\b", re.I),
    "popmenu": re.compile(r"\bpopmenu\b", re.I),
    "chownow": re.compile(r"\bchownow\b", re.I),
    "olo": re.compile(r"\bolo\b", re.I),
}


_IFRAME_REGEX = re.compile(
    r'<iframe[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

_SCRIPT_SRC_REGEX = re.compile(
    r'<script[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _extract_domain(url: Optional[str]) -> str:
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain
    except Exception:
        return ""


def _is_delivery(domain: str) -> bool:
    return any(d in domain for d in _DELIVERY_PATTERNS)


def _score_provider_match(domain: str, html: str) -> Dict[str, int]:
    scores: Dict[str, int] = {}

    for provider, patterns in _PROVIDER_PATTERNS.items():
        score = 0

        for p in patterns:
            if domain and p in domain:
                score += 5

        for p in patterns:
            if html and p in html:
                score += 2

        regex = _SCRIPT_PROVIDER_REGEX.get(provider)
        if regex and html and regex.search(html):
            score += 3

        if score > 0:
            scores[provider] = score

    return scores


def _pick_best_provider(scores: Dict[str, int]) -> Optional[str]:
    if not scores:
        return None
    return max(scores.items(), key=lambda x: x[1])[0]


def detect_provider_from_url(url: Optional[str]) -> Optional[str]:
    domain = _extract_domain(url)

    if not domain:
        return None

    if _is_delivery(domain):
        return None

    if "toasttab.com" in domain:
        return "toast"

    if "squareup.com" in domain or "square.site" in domain:
        return "square"

    scores = _score_provider_match(domain, "")
    return _pick_best_provider(scores)


def _detect_from_script_src(html: str) -> Optional[str]:
    for src in _SCRIPT_SRC_REGEX.findall(html):
        provider = detect_provider_from_url(src)
        if provider:
            return provider
    return None


def _detect_from_iframes(html: str) -> Optional[str]:
    for src in _IFRAME_REGEX.findall(html):
        provider = detect_provider_from_url(src)
        if provider:
            return provider
    return None


def detect_provider_from_html(html: str) -> Optional[str]:
    if not html:
        return None

    html_lower = html.lower()

    provider = _detect_from_iframes(html_lower)
    if provider:
        return provider

    provider = _detect_from_script_src(html_lower)
    if provider:
        return provider

    scores = _score_provider_match("", html_lower)
    return _pick_best_provider(scores)


def detect_provider(
    html: str,
    url: Optional[str] = None,
) -> Optional[str]:
    provider = detect_provider_from_url(url)
    if provider:
        return provider

    return detect_provider_from_html(html)