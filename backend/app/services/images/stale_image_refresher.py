from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.services.images.google_image_fetcher import GoogleImageFetcher
from app.services.images.google_photo_downloader import fetch_photo_bytes
from app.services.upload.r2_client import generate_public_url, upload_bytes


logger = logging.getLogger(__name__)

UTC = timezone.utc

_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _extension_for(content_type: str) -> str:
    return _CONTENT_TYPE_EXT.get(content_type, ".jpg")


class StaleImageRefresher:
    """
    Replaces a place's existing primary image in place with a durably-
    stored copy, instead of routing a stale Google photo reference through
    ImageIngestService's normal gallery-rebuild pipeline.

    That path was deliberately avoided here: Google's Places API (New)
    photo resource names are session-scoped, not stable identifiers for
    "the same photo" across separate API calls, so a fresh
    GoogleImageFetcher.fetch() for a place that already has images returns
    reference strings that won't match anything already in
    place_images.url — MaterializeImageTruth's dedup keys on that exact
    string. Running the full pipeline on every periodic stale-refresh
    cycle (see ImageWorker._select_places' stale reserve) would therefore
    accumulate a fresh, never-pruned set of gallery rows for the same place
    every ~30 days indefinitely, not just replace what's already there.

    Updating the known existing primary row directly sidesteps that
    entirely — there's no dedup question when we already know exactly
    which row we're refreshing. It also means this photo, once refreshed,
    is a real, durable copy we own (R2), not another ephemeral Google
    reference on the same expiry clock as the one it replaced.
    """

    def __init__(
        self,
        *,
        fetcher: Optional[GoogleImageFetcher] = None,
        download_fn: Callable[[str], Optional[Tuple[bytes, str]]] = fetch_photo_bytes,
        upload_fn: Callable[..., None] = upload_bytes,
        public_url_fn: Callable[[str], str] = generate_public_url,
    ) -> None:
        self.fetcher = fetcher or GoogleImageFetcher()
        self.download_fn = download_fn
        self.upload_fn = upload_fn
        self.public_url_fn = public_url_fn

    def refresh_primary(self, *, db: Session, place: Place) -> bool:
        place_id = getattr(place, "id", None)
        if not place_id:
            return False

        primary = db.execute(
            select(PlaceImage).where(
                PlaceImage.place_id == place_id,
                PlaceImage.is_primary.is_(True),
            )
        ).scalars().first()

        # Nothing to refresh in place — this reserve only ever selects
        # places that already have a primary image (see
        # ImageWorker._stale_primary_clause), but stay defensive rather
        # than assume that invariant always holds by the time we get here.
        if not primary:
            logger.debug("stale_image_refresh_no_primary place_id=%s", place_id)
            return False

        try:
            candidates = self.fetcher.fetch(place=place)
        except Exception as exc:
            logger.warning("stale_image_refresh_fetch_failed place_id=%s error=%s", place_id, exc)
            return False

        if not candidates:
            logger.info("stale_image_refresh_no_candidates place_id=%s", place_id)
            return False

        photo_name = candidates[0].get("url")
        if not photo_name:
            return False

        downloaded = self.download_fn(photo_name)
        if not downloaded:
            logger.info(
                "stale_image_refresh_download_failed place_id=%s ref=%s",
                place_id, photo_name,
            )
            return False

        data, content_type = downloaded
        key = f"google-photos/{place_id}/{uuid.uuid4().hex}{_extension_for(content_type)}"

        try:
            self.upload_fn(key=key, data=data, content_type=content_type)
            public_url = self.public_url_fn(key)
        except Exception as exc:
            logger.warning("stale_image_refresh_upload_failed place_id=%s error=%s", place_id, exc)
            return False

        primary.url = public_url
        # Resets the staleness clock _stale_primary_clause checks — this
        # row is now a fresh, durable copy, not the thing that made this
        # place eligible for the reserve in the first place.
        primary.created_at = _utcnow()

        logger.info("stale_image_refresh_ok place_id=%s key=%s", place_id, key)
        return True
