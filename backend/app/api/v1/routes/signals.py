"""
Signal intake API.

Accepts external signals from any data source:
- creator: TikTok/Instagram/YouTube mentions (value = mention strength 0-1)
- award: Michelin, Eater, Infatuation, local awards (value = 1.0 for Michelin star, 0.7 for Bib Gourmand, etc.)
- blog: Food blog mention, curated list inclusion (value = publication authority 0-1)
- save: User saves (for internal use)
- review: External review signal (value = normalized rating)

Deduplication: (place_id, provider, signal_type, external_event_id) is unique.
"""
from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal
from app.core.auth import require_api_key
from app.services.social.platform_detect import detect_platform
from app.services.social.url_normalize import normalize_url
from app.services.social.extractors.tiktok import extract_from_tiktok
from app.services.social.extractors.instagram import extract_from_instagram
from app.services.social.extractors.youtube import extract_from_youtube
from app.services.pipeline.pipeline_runner import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

UTC = timezone.utc

VALID_SIGNAL_TYPES = {"creator", "award", "blog", "save", "review", "trending", "mention"}
VALID_PROVIDERS = {
    "google", "yelp", "tiktok", "instagram", "youtube",
    "michelin", "eater", "infatuation", "internal", "grubhub", "generic",
}


class SignalIntakeRequest(BaseModel):
    place_id: str = Field(..., description="Place UUID")
    signal_type: str = Field(
        ..., description="Signal type: creator|award|blog|save|review|trending|mention"
    )
    provider: str = Field(
        ..., description="Data source: google|yelp|tiktok|michelin|eater|internal|..."
    )
    value: float = Field(..., ge=0.0, le=1.0, description="Normalized signal value 0.0-1.0")
    raw_value: Optional[str] = Field(
        None, description="Raw value before normalization (e.g., '3 stars', '4.5/5')"
    )
    external_event_id: str = Field(
        ..., description="Unique ID in source system (e.g., TikTok video ID, award year)"
    )


class SignalIntakeResponse(BaseModel):
    success: bool
    signal_id: Optional[str] = None
    duplicate: bool = False
    message: str


@router.post("/intake", response_model=SignalIntakeResponse, status_code=201)
def intake_signal(
    body: SignalIntakeRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> SignalIntakeResponse:
    """
    Accept an external signal for a place.

    Returns 201 on success, 200 with duplicate=True if already ingested,
    404 if place not found, 400 if signal_type or provider is invalid.
    """
    # Validate signal_type
    if body.signal_type not in VALID_SIGNAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid signal_type '{body.signal_type}'. "
                f"Valid: {sorted(VALID_SIGNAL_TYPES)}"
            ),
        )

    # Validate provider
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid provider '{body.provider}'. "
                f"Valid: {sorted(VALID_PROVIDERS)}"
            ),
        )

    # Verify place exists and is active
    place = db.get(Place, body.place_id)
    if not place or not place.is_active:
        raise HTTPException(status_code=404, detail=f"Place {body.place_id} not found")

    # Create signal
    signal = PlaceSignal(
        place_id=body.place_id,
        signal_type=body.signal_type,
        provider=body.provider,
        value=body.value,
        raw_value=body.raw_value,
        external_event_id=body.external_event_id,
    )

    try:
        db.add(signal)
        db.commit()
        db.refresh(signal)

        logger.info(
            "signal_ingested place_id=%s signal_type=%s provider=%s value=%s",
            body.place_id,
            body.signal_type,
            body.provider,
            body.value,
        )

        return SignalIntakeResponse(
            success=True,
            signal_id=str(signal.id),
            duplicate=False,
            message="Signal ingested successfully",
        )

    except IntegrityError:
        db.rollback()
        logger.debug(
            "signal_duplicate place_id=%s signal_type=%s external_event_id=%s",
            body.place_id,
            body.signal_type,
            body.external_event_id,
        )
        return SignalIntakeResponse(
            success=True,
            signal_id=None,
            duplicate=True,
            message="Signal already ingested (duplicate)",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("signal_intake_failed place_id=%s error=%s", body.place_id, exc)
        raise HTTPException(status_code=500, detail="Signal intake failed")


_EXTRACTORS = {
    "tiktok": extract_from_tiktok,
    "instagram": extract_from_instagram,
    "youtube": extract_from_youtube,
}


class SocialIntakeRequest(BaseModel):
    url: str = Field(..., description="Social media URL (TikTok/Instagram/YouTube)")
    place_name: str = Field(..., min_length=2, description="Place name hint from caption/context")
    city_hint: Optional[str] = Field(None, description="City name or slug hint")


class SocialIntakeResponse(BaseModel):
    platform: str
    normalized_url: str
    pipeline_result: dict


@router.post("/social-intake", response_model=SocialIntakeResponse, status_code=202)
def social_intake(
    body: SocialIntakeRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> SocialIntakeResponse:
    """
    Accept a social media URL with a place name hint.

    Normalizes the URL, detects the platform, extracts creator context,
    and routes through the pipeline runner for place resolution and signal writing.
    Returns 202 (accepted) — resolution is best-effort.
    """
    normalized = normalize_url(body.url)
    platform = detect_platform(normalized)

    extractor = _EXTRACTORS.get(platform)
    extracted = extractor(normalized) if extractor else {
        "platform": platform,
        "creator_handle": None,
        "confidence": 0.20,
        "source_url": normalized,
        "place_name_hint": None,
    }

    record = {
        "name": body.place_name.strip(),
        "source_platform": extracted["platform"],
        "source_url": extracted["source_url"],
        "confidence": extracted["confidence"],
        "city_hint": body.city_hint,
        "metadata": {"creator_handle": extracted.get("creator_handle")},
    }

    result = run_pipeline([record], db=db, commit=True)

    logger.info(
        "social_intake_processed platform=%s place=%s resolved=%s signals=%s",
        platform,
        body.place_name,
        result.resolved,
        result.signals_written,
    )

    return SocialIntakeResponse(
        platform=platform,
        normalized_url=normalized,
        pipeline_result={
            "normalized": result.normalized,
            "resolved": result.resolved,
            "unresolved": result.unresolved,
            "signals_written": result.signals_written,
            "discovery_candidates_created": result.discovery_candidates_created,
        },
    )
