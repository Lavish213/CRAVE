# app/services/social/platform_detect.py
from __future__ import annotations


def detect_platform(url: str | None) -> str:
    if not url:
        return "unknown"
    u = url.lower()
    if "tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u:
        return "instagram"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "facebook.com" in u or "fb.com" in u:
        return "facebook"
    if "maps.google" in u or "goo.gl/maps" in u:
        return "google_maps"
    if "yelp.com" in u:
        return "yelp"
    if "grubhub.com" in u:
        return "grubhub"
    if "doordash.com" in u:
        return "doordash"
    if "ubereats.com" in u:
        return "ubereats"
    if "opentable.com" in u:
        return "opentable"
    if "resy.com" in u:
        return "resy"
    if url.startswith("http"):
        return "generic"
    return "generic"
