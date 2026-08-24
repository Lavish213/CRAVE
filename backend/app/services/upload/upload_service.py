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
ALLOWED_PHOTO_TYPES = {"food", "menu"}


# -------------------------
# Step 1: Request Upload
# -------------------------

def create_upload_slot(
    db: Session,
    *,
    place_id: str,
    content_type: str,
    file_size_mb: float,
    uploaded_by: str | None = None,
    photo_type: str = "food",
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

    if photo_type not in ALLOWED_PHOTO_TYPES:
        raise ValueError("Unsupported photo type")

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
        uploaded_by=uploaded_by,
        content_type=photo_type,
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

class UploadForbiddenError(Exception):
    """Raised when the caller doesn't own the image being confirmed."""


def confirm_upload(
    db: Session,
    *,
    image_id: str,
    user_id: str,
) -> bool:
    """
    Marks upload as ready for processing. Returns True if this call
    actually performed that transition, False if it was a no-op (see
    below) -- callers should only schedule process_image_upload() when
    this returns True.

    Two guards, both load-bearing:

    - Ownership: image_ids are public (any place's GET /place/{id}
      returns them for its gallery), so without this check any
      authenticated user could confirm-replay any other user's upload.

    - Status must be "pending": this is the actual fix for a confirmed
      self-inflicted data-loss bug. Without it, re-confirming an
      already-"ready" image forces its status back to "processing" and
      re-triggers process_image_upload(), which re-downloads, re-hashes,
      and re-runs the dedup check (app/services/upload/dedup.py) against
      the same image's own already-stored phash -- matching itself as a
      "duplicate" and permanently marking a legitimate, already-published
      photo status="failed". process_image_upload() itself already
      refuses to touch anything not in ("processing", "pending") -- the
      whole hole existed only because this function was unconditionally
      forcing status back into that set regardless of where it already
      was. A repeat confirm (client retry, or someone replaying a stale
      request) is now a silent, idempotent no-op instead.
    """

    image = db.query(PlaceImage).filter(PlaceImage.id == image_id).first()

    if not image:
        raise ValueError("Image not found")

    if image.uploaded_by != user_id:
        raise UploadForbiddenError("You don't own this upload")

    if image.status != "pending":
        return False

    image.status = "processing"
    db.commit()
    return True