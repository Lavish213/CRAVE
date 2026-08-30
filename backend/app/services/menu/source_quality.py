from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def normalize_http_source(value: Any) -> str | None:
    """Return a fetchable public HTTP(S) URL or ``None``."""
    try:
        candidate = str(value or "").strip()
        parsed = urlparse(candidate)
    except Exception:
        return None
    hostname = (parsed.hostname or "").strip().lower()
    if parsed.scheme not in {"http", "https"} or not hostname or "." not in hostname:
        return None
    return candidate


def best_usable_source(*values: Any) -> str | None:
    for value in values:
        normalized = normalize_http_source(value)
        if normalized:
            return normalized
    return None
