from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.models.food_contribution import (
    FoodContribution,
    INTENT_PRIVATE_LOG,
    INTENT_SOCIAL_POST,
    REACTION_GOOD,
    REACTION_LOVED,
    REACTION_NOT_FOR_ME,
    STATUS_COMMITTED,
    STATUS_DELETED,
    VISIBILITY_CONNECTIONS,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.place_video import PlaceVideo
from app.db.session import get_db
from app.services.visit_evidence_service import retract_source, upsert_declared_source

router = APIRouter(prefix="/contributions", tags=["contributions"])


class ContributionCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)
    place_id: str = Field(min_length=1, max_length=36)
    intent: str
    reaction: str | None = None
    caption: str | None = Field(default=None, max_length=2000)
    visibility: str
    occurred_at: datetime | None = None
    image_id: str | None = Field(default=None, max_length=36)
    video_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def validate_semantics(self) -> "ContributionCreate":
        if self.intent not in {INTENT_PRIVATE_LOG, INTENT_SOCIAL_POST}:
            raise ValueError("invalid contribution intent")
        if self.reaction not in {None, REACTION_LOVED, REACTION_GOOD, REACTION_NOT_FOR_ME}:
            raise ValueError("invalid reaction")
        if self.visibility not in {VISIBILITY_PRIVATE, VISIBILITY_CONNECTIONS, VISIBILITY_PUBLIC}:
            raise ValueError("invalid visibility")
        if self.image_id and self.video_id:
            raise ValueError("a contribution may reference one media asset, not both")
        if self.intent == INTENT_PRIVATE_LOG and self.visibility != VISIBILITY_PRIVATE:
            raise ValueError("private logs must remain private")
        if self.intent == INTENT_SOCIAL_POST:
            if self.visibility == VISIBILITY_PRIVATE:
                raise ValueError("social posts require an explicit social audience")
            if not (self.image_id or self.video_id):
                raise ValueError("social posts require media")
        if self.occurred_at and self.occurred_at > datetime.now(timezone.utc):
            raise ValueError("occurred_at cannot be in the future")
        return self


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    place_id: str
    intent: str
    reaction: str | None
    caption: str | None
    visibility: str
    occurred_at: datetime | None
    image_id: str | None
    video_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


def _owned_media_or_404(
    db: Session, *, user_id: str, place_id: str, image_id: str | None, video_id: str | None
) -> None:
    if image_id:
        image = db.query(PlaceImage).filter(PlaceImage.id == image_id).one_or_none()
        if image is None or image.place_id != place_id or image.uploaded_by != user_id:
            raise HTTPException(status_code=404, detail="Media not found")
    if video_id:
        video = db.query(PlaceVideo).filter(PlaceVideo.id == video_id).one_or_none()
        if video is None or video.place_id != place_id or video.uploaded_by != user_id:
            raise HTTPException(status_code=404, detail="Media not found")


@router.post(
    "",
    response_model=ContributionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def create_contribution(
    payload: ContributionCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> FoodContribution:
    existing = (
        db.query(FoodContribution)
        .filter(FoodContribution.user_id == user_id, FoodContribution.client_id == payload.client_id)
        .one_or_none()
    )
    if existing is not None:
        if existing.status == STATUS_DELETED:
            raise HTTPException(status_code=409, detail="Contribution was deleted")
        return existing

    if db.query(Place.id).filter(Place.id == payload.place_id).first() is None:
        raise HTTPException(status_code=404, detail="Place not found")

    _owned_media_or_404(
        db,
        user_id=user_id,
        place_id=payload.place_id,
        image_id=payload.image_id,
        video_id=payload.video_id,
    )

    contribution = FoodContribution(
        user_id=user_id,
        client_id=payload.client_id,
        place_id=payload.place_id,
        intent=payload.intent,
        reaction=payload.reaction,
        caption=payload.caption.strip() if payload.caption and payload.caption.strip() else None,
        visibility=payload.visibility,
        occurred_at=payload.occurred_at,
        image_id=payload.image_id,
        video_id=payload.video_id,
        status=STATUS_COMMITTED,
    )
    db.add(contribution)
    try:
        db.flush()
        upsert_declared_source(
            db,
            user_id=user_id,
            place_id=payload.place_id,
            source="food_contribution",
            source_ref=contribution.id,
            occurred_at=payload.occurred_at,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(FoodContribution)
            .filter(FoodContribution.user_id == user_id, FoodContribution.client_id == payload.client_id)
            .one_or_none()
        )
        if existing is None:
            raise
        return existing
    db.refresh(contribution)
    return contribution


@router.get(
    "/{contribution_id}",
    response_model=ContributionOut,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def get_contribution(
    contribution_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> FoodContribution:
    contribution = (
        db.query(FoodContribution)
        .filter(
            FoodContribution.id == contribution_id,
            FoodContribution.user_id == user_id,
            FoodContribution.status == STATUS_COMMITTED,
        )
        .one_or_none()
    )
    if contribution is None:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return contribution


@router.delete(
    "/{contribution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def delete_contribution(
    contribution_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    contribution = (
        db.query(FoodContribution)
        .filter(FoodContribution.id == contribution_id, FoodContribution.user_id == user_id)
        .one_or_none()
    )
    if contribution is None or contribution.status == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Contribution not found")

    contribution.status = STATUS_DELETED
    contribution.deleted_at = datetime.now(timezone.utc)
    retract_source(
        db,
        user_id=user_id,
        place_id=contribution.place_id,
        source="food_contribution",
        source_ref=contribution.id,
    )
    db.commit()
