# app/services/images/quality_analyzer.py
"""
Pixel-level quality grading for user-uploaded photos.

MUST run on the ORIGINAL decoded image, before app.utils.image_pipeline's
process_image() touches it. That pipeline runs denoise → sharpen →
autocontrast → saturation; measuring sharpness afterwards would be
measuring our own sharpening filter, not what the user actually shot, and
every photo would look acceptably sharp.

Deliberately pure Pillow — no numpy, no OpenCV. numpy happens to be
importable in dev as a transitive dependency but is NOT in
requirements.txt, so depending on it would be the same latent production
break as the Playwright top-level import in browser_fallback.py.

The existing image_classifier.py is not a substitute: it grades by URL
keyword patterns and Google's photo ordering, and never looks at a single
pixel, so it is structurally unable to say anything about an upload.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageFilter, ImageStat

logger = logging.getLogger(__name__)

# Standard 3x3 discrete Laplacian. Variance of the response is the classic
# focus measure: sharp edges produce a wide spread, blur collapses it.
_LAPLACIAN = ImageFilter.Kernel(
    size=(3, 3),
    kernel=[0, 1, 0, 1, -4, 1, 0, 1, 0],
    scale=1,
    offset=0,
)

# Laplacian variance scales with image size, so everything is measured at a
# fixed working resolution. Without this the same photo would score
# differently depending on the phone that took it.
_WORK_SIZE = 512

# Pixels trimmed from each edge after filtering — see the border note in
# analyze_image(). 2px covers the 1px artifact plus its neighbour.
_BORDER_CROP = 2

# Below this the photo is unusable at any display size we serve (the feed
# card alone requests 800px wide).
MIN_DIMENSION = 400

# Measured on a detailed 900px test image at _WORK_SIZE, after the border
# crop above:
#     flat grey     0.0
#     Gaussian r=12 0.5      r=6  0.7      r=3  18      r=2  115
#     r=1           1016     sharp original 2905
#
# The reject floor is deliberately far below "slightly soft". Rejection is
# permanent and silent from the uploader's point of view, and a shallow
# depth-of-field food shot — the single most common good restaurant photo
# — is genuinely low-variance outside its focal plane. So this only catches
# photos destroyed beyond recognition; everything merely mediocre is
# accepted and handled by ranking it low via quality_score, which decides
# what becomes a place's primary image.
#
# Real uploads will differ from synthetic blur. blur_score is persisted on
# every row precisely so these can be re-tuned against production data
# without re-fetching a single image.
BLUR_REJECT_BELOW = 10.0
BLUR_GOOD_ABOVE = 800.0

# Mean luminance (0-255). Outside this band the photo is essentially a
# black or blown-out frame.
DARK_REJECT_BELOW = 28.0
BRIGHT_REJECT_ABOVE = 232.0


@dataclass(frozen=True)
class QualityReport:
    blur_score: float
    brightness: float
    width: int
    height: int
    quality_score: float
    rejection_reason: Optional[str]

    @property
    def acceptable(self) -> bool:
        return self.rejection_reason is None


def _normalize(value: float, low: float, high: float) -> float:
    """Map value into 0..1 across [low, high], clamped at both ends."""
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def analyze_image(image: Image.Image) -> QualityReport:
    """Grade a decoded, un-processed image. Never raises."""
    width, height = image.size

    try:
        grayscale = image.convert("L")
        # Thumbnail (not resize) preserves aspect ratio, so a panorama and a
        # square are both reduced to comparable detail density.
        working = grayscale.copy()
        working.thumbnail((_WORK_SIZE, _WORK_SIZE), Image.LANCZOS)

        edges = working.filter(_LAPLACIAN)

        # PIL's kernel filter does not process border pixels — it copies
        # them through at their original value. Against a field of near-zero
        # Laplacian response that 1px frame is a huge outlier, and it
        # manufactured a constant variance floor (~127 for a flat grey
        # image, which scored HIGHER than a heavily blurred photo). Crop it
        # off so the score reflects image content only.
        w, h = edges.size
        if w > 2 * _BORDER_CROP and h > 2 * _BORDER_CROP:
            edges = edges.crop(
                (_BORDER_CROP, _BORDER_CROP, w - _BORDER_CROP, h - _BORDER_CROP)
            )

        blur_score = float(ImageStat.Stat(edges).var[0])
        brightness = float(ImageStat.Stat(working).mean[0])
    except Exception as exc:
        # A photo we cannot measure is not automatically a photo we should
        # reject — fall through with neutral values and let the other
        # checks (safety, dedup) decide.
        logger.warning("image_quality_analysis_failed error=%s", exc)
        return QualityReport(
            blur_score=0.0, brightness=128.0, width=width, height=height,
            quality_score=0.5, rejection_reason=None,
        )

    # Order matters for the *diagnosis*, not the verdict. A black frame and
    # a blown-out one both have almost no edge detail — clipping destroys
    # it — so a blur-first check would label every exposure failure
    # "too_blurry". Exposure is the more specific and more actionable
    # reason, so it is tested first and blur becomes the fallback for
    # correctly-exposed but unfocused photos.
    rejection_reason: Optional[str] = None
    if min(width, height) < MIN_DIMENSION:
        rejection_reason = "too_small"
    elif brightness < DARK_REJECT_BELOW:
        rejection_reason = "too_dark"
    elif brightness > BRIGHT_REJECT_ABOVE:
        rejection_reason = "overexposed"
    elif blur_score < BLUR_REJECT_BELOW:
        rejection_reason = "too_blurry"

    # Composite: sharpness dominates, with a penalty for drifting toward
    # either end of the exposure range. Feeds PlaceImage.quality_score,
    # which PlaceImageInvariantService._promote_best_eligible ranks by when
    # electing a new primary — so a sharp photo outranks a murky one for
    # the feed card instead of insertion order deciding it.
    sharpness = _normalize(blur_score, BLUR_REJECT_BELOW, BLUR_GOOD_ABOVE)
    # 1.0 at mid-grey, falling off toward pure black or pure white.
    exposure = 1.0 - abs(brightness - 128.0) / 128.0
    quality_score = max(0.0, min(1.0, 0.75 * sharpness + 0.25 * exposure))

    return QualityReport(
        blur_score=blur_score,
        brightness=brightness,
        width=width,
        height=height,
        quality_score=quality_score,
        rejection_reason=rejection_reason,
    )
