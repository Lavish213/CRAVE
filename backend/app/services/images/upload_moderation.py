# app/services/images/upload_moderation.py
"""
Decides what happens to a user upload: publish it, hold it for a human, or
reject it.

Before this existed, every successfully-processed upload went straight to
status="ready" and was immediately eligible to become a place's primary
image — no safety check, no quality floor, and PlaceImage.is_approved was
hardcoded True at upload with nothing anywhere ever setting it False. The
approval column was decorative and there was no takedown path short of
direct database access.

Shape of the policy follows what Google actually does on Maps rather than
a blanket delay: audit everything, but publish in seconds when nothing
trips. A fixed hold on every upload would punish exactly the contributors
worth keeping. So:

  - hard quality failures (unusably small/blurry/dark) reject outright,
    which keeps them out of the review queue entirely
  - safety rejects are absolute
  - a POSSIBLE safety hit is held for review
  - a scan that was meant to run but failed holds only photos from
    accounts with no track record
  - everything else publishes immediately

Crucially, a deployment with no safety scanning configured publishes
normally rather than holding everything. Holding would not make it safer —
it would make the review queue unbounded and undrainable, because nobody
could accrue the approved uploads needed to become trusted.

Checks run cheapest-first so the paid Vision call only happens for photos
that already passed the free local ones.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.services.images.exif_reader import ExifReport, gps_matches_place, read_exif
from app.services.images.quality_analyzer import QualityReport, analyze_image
from app.services.images.safety_scanner import (
    SafetyReport,
    UNSCANNED,
    is_configured as safety_scanning_configured,
    scan_image_url,
)

logger = logging.getLogger(__name__)

# Moderation states. Distinct from PlaceImage.status (which tracks the
# processing lifecycle: pending/processing/ready/failed) — a photo can be
# processed successfully and still be withheld.
MOD_APPROVED = "approved"
MOD_PENDING_REVIEW = "pending_review"
MOD_REJECTED = "rejected"
MOD_STATES = frozenset({MOD_APPROVED, MOD_PENDING_REVIEW, MOD_REJECTED})

# Uploads a contributor needs before their photos publish without a safety
# scan backing them. Low on purpose: this is a spam-burst speed bump, not
# an initiation rite. A verified GPS match bypasses it entirely.
TRUSTED_UPLOAD_COUNT = 3


@dataclass(frozen=True)
class ModerationDecision:
    status: str
    reason: Optional[str]
    quality: QualityReport
    exif: ExifReport
    safety: SafetyReport
    gps_verified: bool

    @property
    def is_publishable(self) -> bool:
        return self.status == MOD_APPROVED


def _prior_approved_uploads(db: Session, user_id: Optional[str]) -> int:
    if not user_id:
        return 0
    return (
        db.query(PlaceImage.id)
        .filter(
            PlaceImage.uploaded_by == user_id,
            PlaceImage.moderation_status == MOD_APPROVED,
        )
        .count()
    )


def screen_upload(
    db: Session,
    *,
    image: PlaceImage,
    original: Image.Image,
    public_url: Optional[str],
    quality: Optional[QualityReport] = None,
    exif: Optional[ExifReport] = None,
) -> ModerationDecision:
    """
    Screen a decoded upload.

    `original` MUST be the image as decoded from the user's bytes, before
    app.utils.image_pipeline.process_image() runs — that pipeline sharpens
    and strips EXIF, which would invalidate both the blur measurement and
    the GPS read.

    `quality`/`exif` let a caller that already ran the cheap local checks
    (to bail out before paying for an R2 write and a Vision call) hand the
    results in rather than recomputing them.
    """
    # 1. EXIF — read before anything strips it.
    if exif is None:
        exif = read_exif(original)

    place = db.query(Place).filter(Place.id == image.place_id).one_or_none()
    gps_verified = gps_matches_place(
        exif,
        place_lat=getattr(place, "lat", None),
        place_lng=getattr(place, "lng", None),
    )

    # 2. Quality — free, local, and rejects outright so junk never reaches
    #    the review queue or the paid scan.
    if quality is None:
        quality = analyze_image(original)
    if not quality.acceptable:
        return ModerationDecision(
            status=MOD_REJECTED,
            reason=quality.rejection_reason,
            quality=quality,
            exif=exif,
            safety=UNSCANNED,
            gps_verified=gps_verified,
        )

    # 3. Safety — the only paid step, so it runs last and only on photos
    #    that already cleared the free checks.
    safety = scan_image_url(public_url) if public_url else UNSCANNED

    if safety.is_reject:
        return ModerationDecision(
            status=MOD_REJECTED,
            reason=f"safety_{safety.detail or 'violation'}",
            quality=quality, exif=exif, safety=safety, gps_verified=gps_verified,
        )

    if safety.needs_review:
        return ModerationDecision(
            status=MOD_PENDING_REVIEW,
            reason=f"safety_review_{safety.detail or 'flagged'}",
            quality=quality, exif=exif, safety=safety, gps_verified=gps_verified,
        )

    # 4. A photo we meant to scan but couldn't is a different thing from a
    #    photo we never intended to scan.
    #
    #    Scanning CONFIGURED but failed (API down, quota, bad response):
    #    transient, so be cautious with accounts that have no track record.
    #    A GPS match skips the wait — it means someone was physically at
    #    the place, which is stronger evidence than any tenure count.
    #
    #    Scanning NOT configured at all: the operator has opted out, and
    #    holding every photo would not make them safer — it would just
    #    guarantee an unbounded review queue nobody can drain, since no one
    #    could ever accumulate approved uploads to become trusted. Publish
    #    and rely on the quality floor plus user reports, which is the
    #    posture the deployment already chose.
    if not safety.scanned and safety_scanning_configured() and not gps_verified:
        if _prior_approved_uploads(db, image.uploaded_by) < TRUSTED_UPLOAD_COUNT:
            return ModerationDecision(
                status=MOD_PENDING_REVIEW,
                reason="scan_unavailable_new_contributor",
                quality=quality, exif=exif, safety=safety, gps_verified=gps_verified,
            )

    return ModerationDecision(
        status=MOD_APPROVED,
        reason=None,
        quality=quality, exif=exif, safety=safety, gps_verified=gps_verified,
    )


def apply_decision(image: PlaceImage, decision: ModerationDecision) -> None:
    """Write a decision onto the image row. Does not commit."""
    image.moderation_status = decision.status
    image.moderation_reason = decision.reason
    image.quality_score = decision.quality.quality_score
    image.blur_score = decision.quality.blur_score
    image.gps_verified = decision.gps_verified
    image.safety_scanned = decision.safety.scanned
    # is_approved was previously written True at upload and never changed.
    # It now means what its name says.
    image.is_approved = decision.status == MOD_APPROVED
