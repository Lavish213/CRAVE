from __future__ import annotations

import uuid


def build_image_id() -> str:
    return str(uuid.uuid4())


def build_orig_key(place_id: str, image_id: str) -> str:
    place_id = str(place_id).strip()
    image_id = str(image_id).strip()
    return f"places/{place_id}/orig/{image_id}.jpg"


def build_processed_key(place_id: str, image_id: str) -> str:
    place_id = str(place_id).strip()
    image_id = str(image_id).strip()
    return f"places/{place_id}/processed/{image_id}.jpg"


def build_thumb_key(place_id: str, image_id: str) -> str:
    place_id = str(place_id).strip()
    image_id = str(image_id).strip()
    return f"places/{place_id}/thumbs/{image_id}.jpg"