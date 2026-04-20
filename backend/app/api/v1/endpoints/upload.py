from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.upload.upload_service import (
    create_upload_slot,
    confirm_upload,
)
from app.workers.image_processing_worker import process_image_upload


router = APIRouter(prefix="/upload", tags=["upload"])


# -------------------------
# Request Upload URL
# -------------------------

@router.post("/request")
def request_upload(
    place_id: str,
    content_type: str,
    file_size_mb: float,
    db: Session = Depends(get_db),
):
    try:
        result = create_upload_slot(
            db=db,
            place_id=place_id,
            content_type=content_type,
            file_size_mb=file_size_mb,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------
# Confirm Upload
# -------------------------

@router.post("/confirm")
def confirm_upload_endpoint(
    image_id: str,
    db: Session = Depends(get_db),
):
    try:
        confirm_upload(
            db=db,
            image_id=image_id,
        )

        # 🔥 trigger async processing (non-blocking)
        process_image_upload(image_id)

        return {"ok": True}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -------------------------
# Poll Status
# -------------------------

@router.get("/status/{image_id}")
def get_upload_status(
    image_id: str,
    db: Session = Depends(get_db),
):
    from app.db.models.place_image import PlaceImage

    image = (
        db.query(PlaceImage)
        .filter(PlaceImage.id == image_id)
        .first()
    )

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    return {
        "status": image.status,
        "error": image.error_message,
    }