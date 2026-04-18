from __future__ import annotations

import logging
import re
from urllib.parse import quote

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["image"])

_MAX_WIDTH = 1600
_TIMEOUT = 10

# Google Places photo_name format: "places/{place_id}/photos/{photo_id}"
# Only allow path segments that match this pattern to prevent SSRF.
_PHOTO_REF_RE = re.compile(r'^places/[A-Za-z0-9_\-]+/photos/[A-Za-z0-9_\-]+$')


@router.get("/image")
def proxy_image(ref: str = Query(..., description="Google Places photo_name")) -> Response:
    if not _PHOTO_REF_RE.match(ref):
        raise HTTPException(status_code=400, detail="Invalid photo reference")

    api_key = (settings.google_places_api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Image service not configured")

    safe_ref = quote(ref, safe="/")
    url = (
        f"https://places.googleapis.com/v1/{safe_ref}/media"
        f"?maxWidthPx={_MAX_WIDTH}&key={api_key}"
    )

    try:
        resp = requests.get(url, timeout=_TIMEOUT, stream=True)
    except Exception as exc:
        logger.debug("image_proxy_failed ref=%s error=%s", ref, exc)
        raise HTTPException(status_code=502, detail="Image proxy error")

    if resp.status_code != 200:
        logger.debug("image_proxy_upstream_error ref=%s status=%s", ref, resp.status_code)
        raise HTTPException(status_code=404, detail="Image not found")

    return Response(
        content=resp.content,
        media_type=resp.headers.get("Content-Type", "image/jpeg"),
        headers={"Cache-Control": "public, max-age=86400"},
    )
