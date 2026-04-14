# app/services/social/extractors/tiktok.py
from __future__ import annotations
import re
from urllib.parse import urlparse

_HANDLE = re.compile(r"^@?([a-zA-Z0-9._]{1,64})$")


def extract_from_tiktok(url: str) -> dict:
    try:
        path = (urlparse(url).path or "").strip()
        handle = None
        for part in path.split("/"):
            if part.startswith("@"):
                m = _HANDLE.match(part[1:])
                if m:
                    handle = m.group(1)
                    break
        return {"platform": "tiktok", "creator_handle": handle,
                "confidence": 0.40 if handle else 0.0,
                "source_url": url, "place_name_hint": None}
    except Exception:
        return {"platform": "tiktok", "creator_handle": None,
                "confidence": 0.0, "source_url": url, "place_name_hint": None}
