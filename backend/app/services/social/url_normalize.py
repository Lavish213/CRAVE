# app/services/social/url_normalize.py
from __future__ import annotations
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

_TRACKING = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_reader", "utm_viz_id", "utm_pubreferrer",
    "utm_swu", "fbclid", "gclid", "igshid", "mc_cid", "mc_eid",
    "ref", "s",
})


def normalize_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    try:
        p = urlparse(url.strip())
        netloc = p.netloc.lower()
        path = p.path.rstrip("/")
        pairs = [
            (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
            if k.lower() not in _TRACKING
        ]
        result = urlunparse((p.scheme.lower(), netloc, path, p.params, urlencode(pairs), ""))
        return result or None
    except Exception:
        return url
