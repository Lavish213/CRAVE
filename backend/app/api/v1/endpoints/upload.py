from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.services.upload.upload_service import (
    create_upload_slot,
    confirm_upload,
)
from app.workers.image_processing_worker import process_image_upload


router = APIRouter(prefix="/upload", tags=["upload"])


# -------------------------
# Request Upload URL
# -------------------------

@router.post("/request", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def request_upload(
    place_id: str,
    content_type: str,
    file_size_mb: float,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
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

@router.post("/confirm", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def confirm_upload_endpoint(
    image_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        confirm_upload(
            db=db,
            image_id=image_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Non-blocking — returns immediately, processing happens after response
    background_tasks.add_task(process_image_upload, image_id)

    return {"ok": True}


# -------------------------
# Poll Status
# -------------------------

@router.get("/status/{image_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_upload_status(
    image_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
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
