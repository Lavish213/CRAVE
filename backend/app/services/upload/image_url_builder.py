from __future__ import annotations

from typing import Optional, Dict

from app.services.upload.r2_client import generate_file_url
from app.services.upload.key_builder import (
    build_orig_key,
    build_processed_key,
    build_thumb_key,
)


def build_image_urls(
    *,
    place_id: str,
    image_id: str,
    processed_key: Optional[str] = None,
    thumb_key: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Convert stored keys into public URLs.

    We NEVER store full URLs in DB — only keys.
    This reconstructs them safely at read time.
    """

    # -------------------------
    # Keys
    # -------------------------

    orig_key = build_orig_key(place_id, image_id)

    processed_key = processed_key or build_processed_key(place_id, image_id)
    thumb_key = thumb_key or build_thumb_key(place_id, image_id)

    # -------------------------
    # URLs
    # -------------------------

    try:
        orig_url = generate_file_url(orig_key)
    except Exception:
        orig_url = None

    try:
        processed_url = generate_file_url(processed_key)
    except Exception:
        processed_url = None

    try:
        thumb_url = generate_file_url(thumb_key)
    except Exception:
        thumb_url = None

    return {
        "orig_url": orig_url,
        "processed_url": processed_url,
        "thumb_url": thumb_url,
    }