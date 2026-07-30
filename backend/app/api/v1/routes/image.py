from __future__ import annotations

import logging
import re
from urllib.parse import quote

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config.settings import settings
from app.core.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["image"])

# Default width. Feed cards render at 220pt tall and full device width —
# on a 3x device that's ~1290px wide at absolute most, and cards are
# cropped with contentFit="cover" so they never need the full source
# resolution. This previously hardcoded 1600px for EVERY image including
# small feed thumbnails, which meant each card pulled several hundred KB
# to a few MB it then threw away. With ~10 cards visible that saturated
# the connection and images simply never appeared before the client gave
# up. Callers that genuinely need a large image (the place-detail hero
# gallery) can ask for it explicitly via ?w=.
_DEFAULT_WIDTH = 800
_MIN_WIDTH = 200
_MAX_WIDTH = 1600

# Upstream fetch timeout. Kept modest on purpose: a slow Google response
# holds a server thread, and the client has its own (longer) timeout, so
# failing fast here and letting the image show its placeholder beats
# queueing requests behind one stalled fetch.
_TIMEOUT = 10

# Bytes per chunk when relaying the upstream response to the client.
_CHUNK_SIZE = 64 * 1024

# Google Places photo_name format: "places/{place_id}/photos/{photo_id}"
# Only allow path segments that match this pattern to prevent SSRF.
_PHOTO_REF_RE = re.compile(r'^places/[A-Za-z0-9_\-]+/photos/[A-Za-z0-9_\-]+$')


def _clamp_width(value: int | None) -> int:
    if value is None:
        return _DEFAULT_WIDTH
    try:
        n = int(value)
    except Exception:
        return _DEFAULT_WIDTH
    return max(_MIN_WIDTH, min(_MAX_WIDTH, n))


@router.get("/image", dependencies=[Depends(rate_limit)])
def proxy_image(
    ref: str = Query(..., description="Google Places photo_name"),
    w: int | None = Query(
        None,
        description=(
            f"Requested image width in px. Clamped to [{_MIN_WIDTH}, {_MAX_WIDTH}]. "
            f"Defaults to {_DEFAULT_WIDTH}, which is sized for feed/list thumbnails."
        ),
    ),
) -> StreamingResponse:
    if not _PHOTO_REF_RE.match(ref):
        raise HTTPException(status_code=400, detail="Invalid photo reference")

    api_key = (settings.google_places_api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Image service not configured")

    width = _clamp_width(w)

    safe_ref = quote(ref, safe="/")
    url = (
        f"https://places.googleapis.com/v1/{safe_ref}/media"
        f"?maxWidthPx={width}&key={api_key}"
    )

    try:
        resp = requests.get(url, timeout=_TIMEOUT, stream=True)
    except Exception as exc:
        logger.warning("image_proxy_failed ref=%s error=%s", ref, exc)
        raise HTTPException(status_code=502, detail="Image proxy error")

    if resp.status_code != 200:
        logger.warning(
            "image_proxy_upstream_error ref=%s status=%s", ref, resp.status_code
        )
        resp.close()
        raise HTTPException(status_code=404, detail="Image not found")

    def _relay():
        # Stream straight through instead of buffering the whole image in
        # memory (the previous `resp.content` read the entire file before
        # sending a single byte — with one worker and a feed full of
        # images, that both delayed first-byte and multiplied memory use).
        try:
            for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                if chunk:
                    yield chunk
        finally:
            resp.close()

    headers = {
        # A Google photo ref is content-addressed — the bytes behind a
        # given ref don't change — so this is safe to cache hard and
        # mark immutable. Was 1 day, which meant re-downloading the whole
        # feed's images daily for no benefit.
        "Cache-Control": "public, max-age=31536000, immutable",
    }
    content_length = resp.headers.get("Content-Length")
    if content_length:
        headers["Content-Length"] = content_length

    return StreamingResponse(
        _relay(),
        media_type=resp.headers.get("Content-Type", "image/jpeg"),
        headers=headers,
    )
