from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import List

from sqlalchemy.orm import Session
from PIL import Image

from app.config.settings import settings
from app.db.session import SessionLocal
from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_CANDIDATE_PRIMARY,
    VISIBILITY_HIDDEN,
    VISIBILITY_SHOWCASE,
)
from app.services.images.exif_reader import read_exif
from app.services.images.quality_analyzer import analyze_image
from app.services.images.upload_moderation import (
    MOD_REJECTED,
    apply_decision,
    screen_upload,
)

from app.services.upload.r2_client import _get_s3_client, R2_BUCKET, generate_public_url
from app.utils.image_pipeline import process_image, process_thumbnail, save_jpeg
from app.utils.hash import generate_phash
from app.services.upload.dedup import is_duplicate_image
from app.services.images.place_image_invariant_service import PlaceImageInvariantService


logger = logging.getLogger(__name__)

CURRENT_PROCESSING_VERSION = 1

# app/services/images/image_scorer.py's SOURCE_WEIGHTS (used when the
# scraped Google Places ingestion path scores its own candidates) ranks
# sources website=1.0, provider=0.9, google=0.85 — with no entry at all
# for user-uploaded content, which falls through to "unknown"=0.6, the
# same tier as garbage. That scorer never actually runs on uploads (this
# worker is a separate path from ImageIngestService), so it doesn't
# directly gate anything here — but PlaceImageInvariantService's own
# re-election logic (_promote_best_eligible) ranks eligible images by
# confidence, and PlaceImage.confidence defaults to a neutral 0.5 if
# nothing sets it. A verified, real photo of the actual place — taken
# by an actual person — is higher-trust content than a scraped stock
# photo, not equal to or below it, so this is set deliberately above
# that neutral default rather than left to it.
_USER_UPLOAD_CONFIDENCE = 0.75


def _safe_error_message(message: str, limit: int = 500) -> str:
    message = (message or "").strip()
    if len(message) <= limit:
        return message
    return message[: limit - 3] + "..."


def process_image_upload(image_id: str) -> None:
    """
    Background worker for user-uploaded images

    Flow:
    R2 orig → download → process → hash → dedup → upload → DB update
    """

    db: Session = SessionLocal()

    try:
        image: PlaceImage | None = (
            db.query(PlaceImage)
            .filter(PlaceImage.id == image_id)
            .first()
        )

        if not image:
            return

        if image.status not in ("processing", "pending"):
            return

        image.status = "processing"
        db.commit()

        # -------------------------
        # Download original from R2
        # -------------------------

        s3 = _get_s3_client()

        obj = s3.get_object(
            Bucket=R2_BUCKET,
            Key=image.orig_key,
        )

        raw_bytes = obj["Body"].read()

        source_image = Image.open(BytesIO(raw_bytes))

        # -------------------------
        # Screening (ORDER IS CRITICAL)
        # -------------------------
        # Both of these read the image as the user actually shot it:
        #   - EXIF must come off `source_image` before .convert("RGB"),
        #     which does not carry metadata onto the new image, and long
        #     before process_image()'s strip_exif() discards it for good.
        #   - Sharpness must be measured before process_image() runs its
        #     denoise → sharpen chain, or we'd be grading our own filter
        #     and every upload would look acceptably sharp.
        exif_report = read_exif(source_image)
        quality_report = analyze_image(source_image)

        pil_image = source_image.convert("RGB")

        # Bail on unusable photos before paying for an R2 write and a
        # Vision call. Rejected uploads keep status="ready" semantics out
        # of it entirely — they never become visible.
        if not quality_report.acceptable:
            image.status = "failed"
            image.moderation_status = MOD_REJECTED
            image.moderation_reason = quality_report.rejection_reason
            image.quality_score = quality_report.quality_score
            image.blur_score = quality_report.blur_score
            image.is_approved = False
            image.error_message = f"Rejected: {quality_report.rejection_reason}"
            db.commit()
            logger.info(
                "image_upload_rejected image_id=%s reason=%s blur=%.1f",
                image.id, quality_report.rejection_reason, quality_report.blur_score,
            )
            return

        # -------------------------
        # Process images
        # -------------------------

        processed = process_image(pil_image)
        thumb = process_thumbnail(pil_image)

        # -------------------------
        # Hash (processed ONLY)
        # -------------------------

        phash = generate_phash(processed)

        # -------------------------
        # Dedup check
        # -------------------------

        if phash and is_duplicate_image(
            db,
            place_id=image.place_id,
            new_phash=phash,
        ):
            image.status = "failed"
            image.error_message = "Duplicate image detected"
            db.commit()
            return

        # -------------------------
        # Convert to bytes
        # -------------------------

        processed_bytes = save_jpeg(processed)
        thumb_bytes = save_jpeg(thumb)

        # -------------------------
        # Upload processed + thumb
        # -------------------------

        s3.put_object(
            Bucket=R2_BUCKET,
            Key=image.processed_key,
            Body=processed_bytes,
            ContentType="image/jpeg",
        )

        s3.put_object(
            Bucket=R2_BUCKET,
            Key=image.thumb_key,
            Body=thumb_bytes,
            ContentType="image/jpeg",
        )

        # -------------------------
        # Final DB update
        # -------------------------

        # Existing gallery/read paths (get_public_gallery,
        # get_primary_image_urls_bulk, primary_image_url_subquery) all read
        # `.url` directly — derive it here so uploaded photos show up
        # through those unchanged, same as legacy scraped images.
        image.url = generate_public_url(image.processed_key)
        image.phash = phash
        image.status = "ready"
        image.processing_version = CURRENT_PROCESSING_VERSION
        image.error_message = None
        image.confidence = _USER_UPLOAD_CONFIDENCE

        # -------------------------
        # Moderation decision
        # -------------------------
        # Runs here rather than earlier because the safety scan needs a
        # publicly reachable URL, which only exists once the processed file
        # is in R2. The local checks computed above are handed in so they
        # aren't recomputed.
        decision = screen_upload(
            db,
            image=image,
            original=source_image,
            public_url=image.url,
            quality=quality_report,
            exif=exif_report,
        )
        apply_decision(image, decision)

        if not decision.is_publishable:
            # Held or rejected: keep it out of every read path. Nothing
            # queries hidden images for the gallery, the feed card, or the
            # map pin, so this is inert until a human resolves it.
            image.is_primary = False
            image.visibility_status = VISIBILITY_HIDDEN
            db.commit()
            logger.info(
                "image_upload_withheld image_id=%s status=%s reason=%s",
                image.id, decision.status, decision.reason,
            )
            return

        # A user-uploaded photo defaults to is_primary=False,
        # visibility_status="gallery_only" (PlaceImage's column defaults),
        # so it shows in the place-detail gallery but never as the feed
        # card / map pin thumbnail — both of those only ever query
        # is_primary=True. Meanwhile ImageIngestService.ingest_place_images
        # historically skipped a place the moment it had *any* image at
        # all, primary or not (it now requires a complete gallery).
        # Combined at the time, a place's first-ever
        # photo being a user upload was a dead end: it would never become
        # primary, and its mere existence would permanently block the
        # scheduled job from ever fetching a Google Places photo either —
        # the card/pin would show the empty-state fallback forever despite
        # a real photo existing in the place's own gallery.
        #
        # If this place has no primary image yet, this upload becomes it
        # immediately. If one already exists, this doesn't silently
        # displace it (auto-replacing a primary is a real editorial call —
        # is a fresh diner photo actually better than what's there? — not
        # something to guess at here) but it does get marked
        # "candidate_primary" rather than left at the generic
        # "gallery_only" default, since a real photo of the place is a
        # legitimate contender for primary, not just gallery filler.
        existing_primary = (
            db.query(PlaceImage.id)
            .filter(PlaceImage.place_id == image.place_id, PlaceImage.is_primary.is_(True))
            .first()
        )
        if existing_primary is None:
            image.is_primary = True
            image.visibility_status = VISIBILITY_SHOWCASE
        else:
            image.visibility_status = VISIBILITY_CANDIDATE_PRIMARY

        db.commit()

        # Re-run the same invariant repair every other mutator of
        # is_primary/visibility_status calls (image_worker.py,
        # menu_image_bridge.py) — this path never did, purely because it
        # predates that service. Cheap defensive consistency (e.g. two
        # uploads processed concurrently) rather than a load-bearing part
        # of the primary-election logic above, which already handles the
        # common case directly.
        try:
            PlaceImageInvariantService().repair(db=db, place_id=image.place_id)
        except Exception:
            logger.exception(
                "image_upload_invariant_repair_failed place_id=%s", image.place_id,
            )

        # Menu photos get a second, best-effort pass: OCR the text off the
        # photo and feed it into the normal menu ingestion pipeline. Never
        # let a failure here affect the photo itself — it's already saved
        # and marked ready above.
        if image.content_type == "menu":
            try:
                from app.services.menu.ocr.menu_photo_ocr import process_menu_photo
                process_menu_photo(
                    db=db,
                    image_id=image.id,
                    place_id=image.place_id,
                    image_url=image.url,
                )
            except Exception as exc:
                logger.warning(
                    "menu_ocr_failed image_id=%s place_id=%s error=%s",
                    image.id, image.place_id, exc,
                )

    except Exception as e:
        try:
            image = (
                db.query(PlaceImage)
                .filter(PlaceImage.id == image_id)
                .first()
            )

            if image:
                image.status = "failed"
                image.error_message = _safe_error_message(str(e))
                db.commit()
        except Exception:
            pass

    finally:
        db.close()


def reclaim_stale_image_uploads(limit: int = 50) -> int:
    """
    Self-healing sweep for PlaceImage rows stuck in 'pending' or
    'processing' -- process_image_upload() is normally triggered once, as
    a FastAPI BackgroundTask off POST /upload/confirm (unlike videos,
    which run entirely through a scheduler job precisely because ffmpeg/
    ML work is too heavy to run in-process -- see scheduler.py's
    _job_video_processing docstring). A BackgroundTask has no durability:
    if the process serving that request is killed or redeployed while the
    task is mid-flight (which happens on every Railway deploy), the row
    is left stuck at 'processing' forever with nothing to ever revisit
    it -- the frontend's status poll (useImageStatusPoll.ts) then spins
    indefinitely with no way to reach 'ready' or 'failed'.

    Rows past settings.photo_stale_processing_minutes since creation are
    reclaimed by simply calling process_image_upload() again --  it's
    already safe to re-enter (its own guard at the top only skips rows
    NOT in ('processing', 'pending'), so this is exactly the same
    invocation the original BackgroundTask made). A row whose R2 upload
    never actually completed (client crashed before the PUT finished)
    fails cleanly through the function's own existing error handling --
    turning "stuck forever" into a correctly-terminal 'failed' status
    either way, matching the self-healing pattern already established for
    videos (see reject_abandoned_pending_uploads /
    video_processing_worker.py's own stale-processing reclaim).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.photo_stale_processing_minutes
    )

    db: Session = SessionLocal()
    try:
        stale_ids: List[str] = [
            row.id
            for row in (
                db.query(PlaceImage.id)
                .filter(
                    PlaceImage.status.in_(("pending", "processing")),
                    PlaceImage.created_at < cutoff,
                )
                .order_by(PlaceImage.created_at.asc())
                .limit(limit)
                .all()
            )
        ]
    finally:
        db.close()

    for image_id in stale_ids:
        try:
            process_image_upload(image_id)
        except Exception:
            logger.exception(
                "image_processing_reclaim_failed image_id=%s", image_id
            )

    return len(stale_ids)
