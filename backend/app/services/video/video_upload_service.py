from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models.place import Place
from app.db.models.place_video import (
    PlaceVideo,
    STATUS_PENDING,
    STATUS_QUEUED,
    STATUS_REJECTED,
    REJECT_TOO_LARGE,
)
from app.db.models.video_template import VideoTemplate
from app.services.upload.key_builder import build_video_id, build_video_orig_key
from app.services.upload.r2_client import (
    delete_object,
    generate_presigned_upload_url,
    head_object,
)

# Content-Type -> file extension. Preserves the actual container format on
# the orig key (see key_builder.build_video_orig_key's docstring) -- a
# device that records QuickTime (.mov) must not end up with a key named
# .mp4 that isn't actually one.
CONTENT_TYPE_EXTENSIONS = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
}


class UploadForbiddenError(Exception):
    """Raised when the caller doesn't own the video/client_id in question."""


def _existing_client_id_row(db: Session, client_id: str, uploaded_by: str) -> Optional[PlaceVideo]:
    existing = db.query(PlaceVideo).filter(PlaceVideo.client_id == client_id).one_or_none()
    if existing and existing.uploaded_by != uploaded_by:
        raise UploadForbiddenError("client_id belongs to a different user")
    return existing


def request_video_upload_slot(
    db: Session,
    *,
    place_id: str,
    content_type: str,
    uploaded_by: str,
    template_id: Optional[str] = None,
    client_id: Optional[str] = None,
) -> Dict:
    """
    Step 1 of the upload flow: validates the place/template, then issues a
    presigned PUT URL for the client to upload directly to R2.

    client_id makes a retried call idempotent -- an offline-recorded clip
    (see frontend/src/stores/videoQueueStore.ts) resubmits the same
    client_id if the app crashes or loses connectivity between "the
    upload-url call succeeded" and "the PUT actually finished." Rather
    than creating a second PlaceVideo row (and orphaning the first one's
    now-unreferenced storage key), this returns the existing row's own key
    with a freshly-signed URL -- presigned URLs expire (see
    generate_presigned_upload_url's default), so a retry needs a new one
    regardless of whether the row itself is also new.
    """
    if content_type not in CONTENT_TYPE_EXTENSIONS:
        raise ValueError(f"Unsupported content type: {content_type}")

    place = (
        db.query(Place)
        .filter(Place.id == place_id, Place.is_active.is_(True))
        .one_or_none()
    )
    if not place:
        raise ValueError("Place not found")

    if template_id:
        template = (
            db.query(VideoTemplate)
            .filter(VideoTemplate.id == template_id, VideoTemplate.active.is_(True))
            .one_or_none()
        )
        if not template:
            raise ValueError("Template not found")

    if client_id:
        existing = _existing_client_id_row(db, client_id, uploaded_by)
        if existing:
            upload_url = generate_presigned_upload_url(key=existing.orig_key, content_type=content_type)
            return {"video_id": existing.id, "upload_url": upload_url, "key": existing.orig_key}

    video_id = build_video_id()
    ext = CONTENT_TYPE_EXTENSIONS[content_type]
    key = build_video_orig_key(place_id, video_id, ext)

    video = PlaceVideo(
        id=video_id,
        place_id=place_id,
        uploaded_by=uploaded_by,
        template_id=template_id,
        client_id=client_id,
        orig_key=key,
        status=STATUS_PENDING,
    )
    db.add(video)
    try:
        db.commit()
    except IntegrityError:
        # Lost a genuine race: a concurrent retry with the same client_id
        # (e.g. two overlapping background sync ticks) committed first,
        # between the pre-check above and this commit. The DB's partial
        # unique index on client_id is what actually guarantees only one
        # row ever exists for it -- fall back to reading what the winner
        # created, same as the pre-check path above.
        db.rollback()
        if not client_id:
            raise
        existing = _existing_client_id_row(db, client_id, uploaded_by)
        if not existing:
            raise
        upload_url = generate_presigned_upload_url(key=existing.orig_key, content_type=content_type)
        return {"video_id": existing.id, "upload_url": upload_url, "key": existing.orig_key}

    upload_url = generate_presigned_upload_url(key=key, content_type=content_type)
    return {"video_id": video.id, "upload_url": upload_url, "key": key}


def confirm_video_upload(db: Session, *, video_id: str, user_id: str) -> bool:
    """
    Step 2: client confirms the direct-to-storage PUT finished. Returns
    True if this call actually transitioned the row to 'queued' (ready
    for the processing worker's next batch pickup -- see
    app/services/video/video_processing_worker.py), False if it was a
    no-op.

    Two guards, both load-bearing -- same two, for the same reasons, as
    app/services/upload/upload_service.py's confirm_upload, which had a
    confirmed real bug (any authenticated user could confirm/reprocess any
    image_id, since image_ids are public) fixed earlier in this same
    review pass:
      - Ownership: video_id must belong to the calling user.
      - Status must be 'pending': a repeat confirm (client retry, or
        someone replaying a stale request) is a no-op, not a re-queue --
        re-running the ffmpeg/food-score pipeline on an already-processed
        video would be wasted work at best.

    Also enforces settings.video_max_upload_mb here, for the same reason
    the Node reference this was ported from does: a presigned PUT URL has
    no built-in size cap, so this -- the first point after the upload
    actually lands -- is the real enforcement point. Checking via
    head_object (no download) instead of leaving it to the worker means
    an oversized file never costs a download + ffmpeg/classifier run it's
    guaranteed to fail anyway.
    """
    video = db.query(PlaceVideo).filter(PlaceVideo.id == video_id).one_or_none()
    if not video:
        raise ValueError("Video not found")

    if video.uploaded_by != user_id:
        raise UploadForbiddenError("You don't own this upload")

    if video.status != STATUS_PENDING:
        return False

    try:
        meta = head_object(video.orig_key)
    except Exception as exc:
        raise ValueError("Upload not found in storage yet") from exc

    size_bytes = meta.get("ContentLength") or 0
    max_bytes = settings.video_max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        delete_object(video.orig_key)
        video.status = STATUS_REJECTED
        video.reject_reason = REJECT_TOO_LARGE
        db.commit()
        raise ValueError(f"File exceeds max upload size ({settings.video_max_upload_mb}MB)")

    video.status = STATUS_QUEUED
    db.commit()
    return True
