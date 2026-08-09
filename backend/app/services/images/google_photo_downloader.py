from __future__ import annotations

import logging
import re
from typing import Optional, Tuple
from urllib.parse import quote

import requests

from app.config.settings import settings


logger = logging.getLogger(__name__)

# Same pattern app/api/v1/routes/image.py validates against before proxying
# — a Google Places (New) photo resource name, "places/{id}/photos/{id}".
# Re-checked here too since this module has its own, separate caller
# (the stale-image refresh path) and shouldn't trust an unvalidated string
# into an outbound request just because some other code path already
# checked its own copy.
_PHOTO_REF_RE = re.compile(r'^places/[A-Za-z0-9_\-]+/photos/[A-Za-z0-9_\-]+$')

_DEFAULT_WIDTH = 1600
_TIMEOUT = 10


def fetch_photo_bytes(photo_name: str, *, width: int = _DEFAULT_WIDTH) -> Optional[Tuple[bytes, str]]:
    """
    Download the actual image bytes for a Google Places (New) photo
    resource name. Returns (bytes, content_type) on success, None on any
    failure — this backs an automatic background refresh cycle, not a
    user-facing request, so there's no one to show an error to; the
    caller's own retry/backoff bookkeeping is what matters here, not this
    function surfacing why.
    """
    if not _PHOTO_REF_RE.match(photo_name):
        logger.warning("google_photo_download_invalid_ref ref=%s", photo_name)
        return None

    api_key = (settings.google_places_api_key or "").strip()
    if not api_key:
        return None

    safe_ref = quote(photo_name, safe="/")
    url = (
        f"https://places.googleapis.com/v1/{safe_ref}/media"
        f"?maxWidthPx={width}&key={api_key}"
    )

    try:
        resp = requests.get(url, timeout=_TIMEOUT)
    except Exception as exc:
        logger.warning("google_photo_download_failed ref=%s error=%s", photo_name, exc)
        return None

    if resp.status_code != 200:
        logger.warning(
            "google_photo_download_upstream_error ref=%s status=%s",
            photo_name, resp.status_code,
        )
        return None

    content_type = resp.headers.get("Content-Type", "image/jpeg")
    return resp.content, content_type
