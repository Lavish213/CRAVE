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

# Upper bound on rows scanned for the near-duplicate (Hamming-distance) pass
# below. Hamming distance has no index to exploit, so this is a genuine
# full scan up to this limit — acceptable at today's catalog size, but if
# PlaceImage grows into the hundreds of thousands this needs a proper
# nearest-neighbor structure (e.g. a BK-tree) instead of scanning rows per
# upload. Exact-match reuse (the common spam case) is checked separately
# below via the indexed phash column and is NOT subject to this limit.
_GLOBAL_SCAN_LIMIT = 20_000


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
    True if new_phash duplicates any existing image ANYWHERE in the
    catalog — not just this place.

    Previously scoped to place_id only, which meant the actual spam pattern
    platforms like Yelp specifically call out — one stock photo seeded
    across dozens of different restaurants — was invisible to it: every
    upload was only ever compared against that one place's own photos, so
    the same file could be re-uploaded to an unlimited number of other
    places without ever tripping this check.

    place_id is accepted for call-site/signature stability and is no
    longer used to scope the query.
    """

    if not new_phash:
        return False

    try:
        new_hash = imagehash.hex_to_hash(new_phash)
    except Exception:
        return False

    # Exact reuse of the same file is the common case (someone re-uploads
    # the identical stock photo) and hits phash's existing index directly,
    # so it's checked first and separately from the bounded scan below.
    exact_match = (
        db.query(PlaceImage.id)
        .filter(PlaceImage.phash == new_phash)
        .first()
    )
    if exact_match:
        return True

    # Near-duplicates (recompressed, cropped, lightly edited copies) need
    # a real Hamming-distance comparison, which has no index to exploit —
    # see _GLOBAL_SCAN_LIMIT above for the scaling caveat.
    rows: List[str] = [
        r[0]
        for r in db.query(PlaceImage.phash)
        .filter(PlaceImage.phash.isnot(None))
        .limit(_GLOBAL_SCAN_LIMIT)
        .all()
    ]

    for existing_phash in rows:
        try:
            existing_hash = imagehash.hex_to_hash(existing_phash)
            distance = new_hash - existing_hash

            if distance <= threshold:
                return True

        except Exception:
            continue

    return False