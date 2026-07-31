from __future__ import annotations

import logging
from io import BytesIO

from sqlalchemy.orm import Session
from PIL import Image

from app.db.session import SessionLocal
from app.db.models.place_image import PlaceImage, VISIBILITY_SHOWCASE

from app.services.upload.r2_client import _get_s3_client, R2_BUCKET, generate_public_url
from app.utils.image_pipeline import process_image, process_thumbnail, save_jpeg
from app.utils.hash import generate_phash
from app.services.upload.dedup import is_duplicate_image


logger = logging.getLogger(__name__)

CURRENT_PROCESSING_VERSION = 1


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

        pil_image = Image.open(BytesIO(raw_bytes)).convert("RGB")

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

        # A user-uploaded photo defaults to is_primary=False,
        # visibility_status="gallery_only" (PlaceImage's column defaults),
        # so it shows in the place-detail gallery but never as the feed
        # card / map pin thumbnail — both of those only ever query
        # is_primary=True. Meanwhile ImageIngestService.ingest_place_images
        # skips a place entirely (unless force_refresh=True, which the
        # scheduled ImageWorker never passes) the moment it has *any*
        # image at all, primary or not. Combined, a place's first-ever
        # photo being a user upload was a dead end: it would never become
        # primary, and its mere existence would permanently block the
        # scheduled job from ever fetching a Google Places photo either —
        # the card/pin would show the empty-state fallback forever despite
        # a real photo existing in the place's own gallery.
        #
        # If this place has no primary image yet, this upload becomes it
        # immediately. Doesn't touch an existing primary — replacing one
        # automatically is a real editorial call (is a fresh diner photo
        # actually better than what's there?) that this fix deliberately
        # leaves alone; it only closes the dead-end where nothing was ever
        # going to become primary at all.
        existing_primary = (
            db.query(PlaceImage.id)
            .filter(PlaceImage.place_id == image.place_id, PlaceImage.is_primary.is_(True))
            .first()
        )
        if existing_primary is None:
            image.is_primary = True
            image.visibility_status = VISIBILITY_SHOWCASE

        db.commit()

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