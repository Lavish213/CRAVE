from __future__ import annotations

from typing import Optional, List

from PIL import Image
import imagehash
from sqlalchemy.orm import Session

from app.db.models.place_image import PlaceImage


# -------------------------
# CONFIG (tunable later)
# -------------------------

DEFAULT_PHASH_THRESHOLD = 8


# -------------------------
# Hash Generation
# -------------------------

def compute_phash(image: Image.Image) -> str:
    """
    Generate perceptual hash from processed image.
    MUST be run on processed image, not original.
    """
    phash = imagehash.phash(image)
    return str(phash)


# -------------------------
# Duplicate Check
# -------------------------

def is_duplicate_image(
    db: Session,
    *,
    place_id: str,
    new_phash: str,
    threshold: int = DEFAULT_PHASH_THRESHOLD,
) -> bool:
    """
    Compare new image hash against existing images for the same place.
    Returns True if duplicate detected.
    """

    if not new_phash:
        return False

    # Fetch existing hashes for this place
    rows: List[PlaceImage] = (
        db.query(PlaceImage.phash)
        .filter(
            PlaceImage.place_id == place_id,
            PlaceImage.phash.isnot(None),
        )
        .all()
    )

    if not rows:
        return False

    try:
        new_hash = imagehash.hex_to_hash(new_phash)
    except Exception:
        return False

    for r in rows:
        try:
            existing_hash = imagehash.hex_to_hash(r.phash)
            distance = new_hash - existing_hash

            if distance <= threshold:
                return True

        except Exception:
            continue

    return False