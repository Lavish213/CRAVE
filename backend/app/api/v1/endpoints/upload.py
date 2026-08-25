from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.services.upload.upload_service import (
    create_upload_slot,
    confirm_upload,
    UploadForbiddenError,
)
from app.workers.image_processing_worker import process_image_upload


router = APIRouter(prefix="/upload", tags=["upload"])


# -------------------------
# Request/response bodies
# -------------------------
# NOTE: these were previously bare scalar function params (place_id: str,
# content_type: str, file_size_mb: float), which FastAPI treats as required
# *query* params for any non-path, non-Pydantic argument — regardless of
# HTTP method. The frontend (frontend/src/api/upload.ts) sends a JSON body,
# matching every other POST route in this app, so every upload request was
# guaranteed to 422 before this fix, independent of R2 config.

class UploadRequestBody(BaseModel):
    place_id: str
    content_type: str
    file_size_mb: float
    # Semantic label for what the photo shows — "food" (default, general
    # gallery) or "menu" (triggers OCR extraction, see
    # app/services/menu/ocr/menu_photo_ocr.py). Distinct from `content_type`
    # above, which is the MIME type of the file being uploaded.
    photo_type: str = "food"


class UploadConfirmBody(BaseModel):
    image_id: str


# -------------------------
# Request Upload URL
# -------------------------

@router.post("/request", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def request_upload(
    payload: UploadRequestBody = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = create_upload_slot(
            db=db,
            place_id=payload.place_id,
            content_type=payload.content_type,
            file_size_mb=payload.file_size_mb,
            uploaded_by=user_id,
            photo_type=payload.photo_type,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------
# Confirm Upload
# -------------------------

@router.post("/confirm", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def confirm_upload_endpoint(
    background_tasks: BackgroundTasks,
    payload: UploadConfirmBody = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        transitioned = confirm_upload(
            db=db,
            image_id=payload.image_id,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except UploadForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Only schedule processing if this call actually moved the image from
    # "pending" -- a repeat confirm is a no-op (see confirm_upload's
    # docstring for why re-processing an already-finalized image is
    # actively destructive, not just wasted work).
    if transitioned:
        background_tasks.add_task(process_image_upload, payload.image_id)

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
        # `status` alone reaches "ready" as soon as processing finishes,
        # regardless of the separate moderation decision (see
        # app/db/models/place_image.py's moderation_status comment) --
        # without this, the caller can't tell a photo that's actually
        # live from one that's silently sitting hidden pending human
        # review, since both report status="ready".
        "moderation_status": image.moderation_status,
        "moderation_reason": image.moderation_reason,
    }
