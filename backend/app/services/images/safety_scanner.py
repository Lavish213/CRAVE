# app/services/images/safety_scanner.py
"""
Google Cloud Vision SafeSearch screening for user uploads.

No new vendor: app/services/menu/ocr/menu_photo_ocr.py already calls
images:annotate with the same GOOGLE_PLACES_API_KEY for menu OCR, so this
reuses the existing key and billing account.

Cost: Vision bills per feature per image, first 1,000 units/month free per
feature, then $1.50/1,000. This sends ONE feature (SAFE_SEARCH_DETECTION)
per upload, so it stays inside the free tier below ~1,000 uploads/month.

Degrades to "unscanned" rather than failing closed when the key is absent
or the API errors: a hard dependency here would mean an outage at Google
silently stops every photo in the app from ever publishing. Callers decide
what an unscanned photo is worth — see upload_moderation.py, which holds
it for review instead of publishing it blind.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from app.services.network.http_fetcher import fetch

logger = logging.getLogger(__name__)

VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"

# Vision returns one of these likelihood buckets per category.
_LIKELIHOOD_RANK = {
    "UNKNOWN": 0,
    "VERY_UNLIKELY": 1,
    "UNLIKELY": 2,
    "POSSIBLE": 3,
    "LIKELY": 4,
    "VERY_LIKELY": 5,
}

# LIKELY or above on any of these blocks the upload outright.
_REJECT_AT = _LIKELIHOOD_RANK["LIKELY"]
# POSSIBLE gets a human look rather than an automatic verdict either way.
_REVIEW_AT = _LIKELIHOOD_RANK["POSSIBLE"]

# "spoof" (a doctored/meme image) and "medical" are deliberately excluded
# from the blocking set: neither is a safety issue for a restaurant photo,
# and medical in particular false-positives on close-up food shots.
_BLOCKING_CATEGORIES = ("adult", "violence", "racy")


@dataclass(frozen=True)
class SafetyReport:
    scanned: bool
    verdict: str  # "clean" | "review" | "reject" | "unscanned"
    detail: Optional[str] = None

    @property
    def is_reject(self) -> bool:
        return self.verdict == "reject"

    @property
    def needs_review(self) -> bool:
        return self.verdict == "review"


UNSCANNED = SafetyReport(scanned=False, verdict="unscanned")


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_PLACES_API_KEY"))


def scan_image_url(image_url: str) -> SafetyReport:
    """Run SafeSearch against a publicly reachable image URL."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        logger.debug("safety_scan_skipped reason=no_api_key")
        return UNSCANNED

    if not image_url:
        return UNSCANNED

    try:
        response = fetch(
            VISION_API_URL,
            method="POST",
            params={"key": api_key},
            json={
                "requests": [{
                    "image": {"source": {"imageUri": image_url}},
                    "features": [{"type": "SAFE_SEARCH_DETECTION"}],
                }]
            },
        )
    except Exception as exc:
        logger.warning("safety_scan_request_failed error=%s", exc)
        return UNSCANNED

    if response is None or getattr(response, "status_code", 0) != 200:
        logger.warning(
            "safety_scan_http_error status=%s",
            getattr(response, "status_code", None),
        )
        return UNSCANNED

    try:
        payload = response.json()
        responses = payload.get("responses") or []
        if not responses:
            return UNSCANNED

        first = responses[0]
        if "error" in first:
            logger.warning("safety_scan_api_error error=%s", first["error"])
            return UNSCANNED

        annotation = first.get("safeSearchAnnotation")
        if not annotation:
            return UNSCANNED
    except Exception as exc:
        logger.warning("safety_scan_parse_failed error=%s", exc)
        return UNSCANNED

    worst_rank = 0
    worst_category = None
    for category in _BLOCKING_CATEGORIES:
        rank = _LIKELIHOOD_RANK.get(str(annotation.get(category, "UNKNOWN")).upper(), 0)
        if rank > worst_rank:
            worst_rank = rank
            worst_category = category

    if worst_rank >= _REJECT_AT:
        return SafetyReport(scanned=True, verdict="reject", detail=worst_category)
    if worst_rank >= _REVIEW_AT:
        return SafetyReport(scanned=True, verdict="review", detail=worst_category)
    return SafetyReport(scanned=True, verdict="clean")
