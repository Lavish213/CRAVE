from __future__ import annotations

import uuid
from typing import Dict

from sqlalchemy.orm import Session

from app.services.upload.key_builder import (
    build_orig_key,
    build_processed_key,
    build_thumb_key,
)
from app.services.upload.r2_client import generate_presigned_upload_url
from app.db.models.place_image import PlaceImage


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 15


# -------------------------
# Step 1: Request Upload
# -------------------------

def create_upload_slot(
    db: Session,
    *,
    place_id: str,
    content_type: str,
    file_size_mb: float,
) -> Dict:
    """
    Creates:
    - image_id
    - R2 upload key
    - signed upload URL
    - DB record (pending)
    """

    # -------------------------
    # Validation
    # -------------------------

    if content_type not in ALLOWED_TYPES:
        raise ValueError("Unsupported file type")

    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ValueError("File too large")

    # -------------------------
    # IDs + Keys
    # -------------------------

    image_id = str(uuid.uuid4())

    orig_key = build_orig_key(place_id, image_id)
    processed_key = build_processed_key(place_id, image_id)
    thumb_key = build_thumb_key(place_id, image_id)

    # -------------------------
    # Signed URL
    # -------------------------

    upload_url = generate_presigned_upload_url(
        key=orig_key,
        content_type=content_type,
    )

    # -------------------------
    # DB Row (PENDING)
    # -------------------------

    image = PlaceImage(
        id=image_id,
        place_id=place_id,
        orig_key=orig_key,
        processed_key=processed_key,
        thumb_key=thumb_key,
        status="pending",
        processing_version=1,
        is_approved=True,
    )

    db.add(image)
    db.commit()

    return {
        "image_id": image_id,
        "upload_url": upload_url,
    }


# -------------------------
# Step 2: Confirm Upload
# -------------------------

def confirm_upload(
    db: Session,
    *,
    image_id: str,
) -> None:
    """
    Marks upload as ready for processing
    """

    image = db.query(PlaceImage).filter(PlaceImage.id == image_id).first()

    if not image:
        raise ValueError("Image not found")

    image.status = "processing"

    db.commit()