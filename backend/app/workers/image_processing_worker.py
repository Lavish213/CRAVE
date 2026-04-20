from __future__ import annotations

from io import BytesIO

from sqlalchemy.orm import Session
from PIL import Image

from app.db.session import SessionLocal
from app.db.models.place_image import PlaceImage

from app.services.upload.r2_client import _get_s3_client, R2_BUCKET
from app.utils.image_pipeline import process_image, process_thumbnail, save_jpeg
from app.utils.hash import generate_phash
from app.services.upload.dedup import is_duplicate_image


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

        image.phash = phash
        image.status = "ready"
        image.processing_version = CURRENT_PROCESSING_VERSION
        image.error_message = None

        db.commit()

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