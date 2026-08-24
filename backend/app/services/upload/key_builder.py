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


# -------------------------
# Video (see app/services/video/)
# -------------------------

def build_video_id() -> str:
    return str(uuid.uuid4())


# Preserves whatever extension the client actually uploaded (see
# app/services/video/video_upload_service.py's CONTENT_TYPE_EXTENSIONS) --
# unlike the processed/thumb keys below, this hasn't been transcoded yet,
# so writing it under a ".mp4" name it might not actually be would confuse
# any tool that infers content-type from the extension.
def build_video_orig_key(place_id: str, video_id: str, ext: str) -> str:
    place_id = str(place_id).strip()
    video_id = str(video_id).strip()
    ext = str(ext).strip().lstrip(".")
    return f"places/{place_id}/videos/orig/{video_id}.{ext}"


# Compression always outputs a real .mp4 container regardless of the
# source extension (see video_processing_worker.py) -- same "the key
# extension must match the actual bytes" lesson as key_builder's other
# processed/thumb keys.
def build_video_processed_key(place_id: str, video_id: str) -> str:
    place_id = str(place_id).strip()
    video_id = str(video_id).strip()
    return f"places/{place_id}/videos/processed/{video_id}.mp4"


def build_video_thumb_key(place_id: str, video_id: str) -> str:
    place_id = str(place_id).strip()
    video_id = str(video_id).strip()
    return f"places/{place_id}/videos/thumbs/{video_id}.jpg"