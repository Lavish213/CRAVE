# app/services/social/extractors/youtube.py
from __future__ import annotations
from urllib.parse import urlparse


def extract_from_youtube(url: str) -> dict:
    try:
        parts = [p for p in (urlparse(url).path or "").split("/") if p]
        handle = None
        if parts:
            if parts[0].startswith("@"):
                handle = parts[0][1:] or None
            elif parts[0] in {"c", "user"} and len(parts) > 1:
                handle = parts[1]
        return {"platform": "youtube", "creator_handle": handle,
                "confidence": 0.30 if handle else 0.0,
                "source_url": url, "place_name_hint": None}
    except Exception:
        return {"platform": "youtube", "creator_handle": None,
                "confidence": 0.0, "source_url": url, "place_name_hint": None}
