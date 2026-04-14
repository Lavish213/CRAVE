# app/services/social/extractors/instagram.py
from __future__ import annotations
import re
from urllib.parse import urlparse

_HANDLE = re.compile(r"^([a-zA-Z0-9._]{1,30})$")
_RESERVED = frozenset({"p", "reel", "explore", "stories", "tv", "direct", "accounts"})


def extract_from_instagram(url: str) -> dict:
    try:
        parts = [p for p in (urlparse(url).path or "").split("/") if p]
        handle = None
        if parts and parts[0] not in _RESERVED:
            m = _HANDLE.match(parts[0])
            if m:
                handle = m.group(1)
        return {"platform": "instagram", "creator_handle": handle,
                "confidence": 0.35 if handle else 0.0,
                "source_url": url, "place_name_hint": None}
    except Exception:
        return {"platform": "instagram", "creator_handle": None,
                "confidence": 0.0, "source_url": url, "place_name_hint": None}
