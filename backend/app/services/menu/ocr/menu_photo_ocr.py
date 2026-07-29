from __future__ import annotations

"""
Menu-photo OCR pipeline.

Concept: instead of guessing at a restaurant's website HTML (the existing
ExtractionController chain — provider parsers, JSON-LD, heuristic HTML,
Playwright escalation), this reads the menu directly from a user-submitted
photo of the physical menu. A photo of the real thing is a much more
reliable source than scraping an arbitrary site's markup — see the
"user_photo_ocr" precedence tier added to menu_source_manager.py.

Flow:
    1. User uploads a photo and tags it as a menu photo (PlaceImage.content_type
       == "menu" — see UploadRequestBody.photo_type in api/v1/endpoints/upload.py).
    2. image_processing_worker.py finishes normal image processing (resize,
       thumbnail, dedup, R2 upload) and, only for menu photos, calls
       process_menu_photo() below as a best-effort extra step.
    3. Google Cloud Vision's TEXT_DETECTION reads the raw text off the photo.
    4. A line-based heuristic groups lines into (name, price) pairs — the same
       "best effort, not perfect" heuristic style as html_menu_extractor.py,
       just applied to OCR output instead of HTML.
    5. Results go through the SAME ingestion pipeline as every other menu
       source (orchestration/ingest_menu_items.py) — normalization, fingerprint
       dedup, canonical materialization — so OCR items compete/merge with
       scraped items using the existing confidence system, not a separate path.

Auth: reuses GOOGLE_PLACES_API_KEY. Cloud Vision and Places API keys both
authenticate via a plain API key on the same GCP project — enable the
"Cloud Vision API" on that project in the Google Cloud Console; no new
credential needs to be issued or added to Railway.
"""

import logging
import os
import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app.services.network.http_fetcher import fetch
from app.services.menu.contracts import ExtractedMenuItem, SOURCE_HTML
from app.services.menu.normalization.price_parser import parse_price
from app.services.menu.orchestration.ingest_menu_items import ingest_menu_items
from app.services.menu.discovery.menu_source_manager import menu_source_manager

logger = logging.getLogger(__name__)

VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"

# Same key as Google Places ingest — see module docstring.
_VISION_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

SOURCE_USER_PHOTO_OCR = "user_photo_ocr"

# Lines shorter than this or without letters are almost never menu items
# (stray punctuation, page numbers, decorative dividers from the photo).
_MIN_NAME_LEN = 2

# A line is treated as a section header (e.g. "APPETIZERS", "Small Plates")
# rather than an item when it has no price and is short + mostly capitalized.
_SECTION_MAX_WORDS = 4


def _get_vision_text(image_url: str) -> Optional[str]:
    """
    Calls Google Cloud Vision TEXT_DETECTION on a public image URL.
    Returns the full extracted text block, or None on any failure.
    """
    if not _VISION_API_KEY:
        logger.warning("menu_ocr_skipped reason=no_api_key")
        return None

    if not image_url:
        return None

    try:
        response = fetch(
            VISION_API_URL,
            method="POST",
            params={"key": _VISION_API_KEY},
            json={
                "requests": [
                    {
                        "image": {"source": {"imageUri": image_url}},
                        "features": [{"type": "TEXT_DETECTION"}],
                    }
                ]
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            logger.warning(
                "menu_ocr_vision_http_error status=%s body=%s",
                response.status_code, response.text[:300],
            )
            return None

        data = response.json()
        results = data.get("responses") or []
        if not results:
            return None

        result = results[0]

        if "error" in result:
            logger.warning("menu_ocr_vision_api_error error=%s", result["error"])
            return None

        full_text = result.get("fullTextAnnotation", {}).get("text")
        return full_text or None

    except Exception as exc:
        logger.warning("menu_ocr_vision_request_failed error=%s", exc)
        return None


def _looks_like_section_header(line: str) -> bool:
    words = line.split()
    if not words or len(words) > _SECTION_MAX_WORDS:
        return False
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio > 0.7


def parse_menu_photo_text(raw_text: str, *, source_url: Optional[str] = None) -> List[ExtractedMenuItem]:
    """
    Line-based heuristic: menu photos usually render as one item (and
    sometimes its price) per line via OCR line-breaking, occasionally with a
    wrapped description on the following line. This is a best-effort parser,
    not a guarantee — same posture as the existing HTML heuristic extractor.
    """
    if not raw_text:
        return []

    items: List[ExtractedMenuItem] = []
    current_section: Optional[str] = None
    pending_item: Optional[ExtractedMenuItem] = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip().strip(".·•-—")
        if not line:
            continue

        price_cents, currency = parse_price(line)

        if price_cents is None and _looks_like_section_header(line):
            current_section = line.title()
            pending_item = None
            continue

        if price_cents is not None:
            # Strip the matched price text (and any leading dot-leaders) off
            # the line to isolate the item name.
            name = re.sub(r"[\.\s]*[\$€£]?\s*\d+(?:[.,]\d{1,2})?\s*$", "", line).strip(" -–—:")
            if len(name) < _MIN_NAME_LEN:
                # Price with no real name — likely a stray line; skip.
                pending_item = None
                continue

            pending_item = ExtractedMenuItem(
                name=name,
                section=current_section,
                price_cents=price_cents,
                currency=currency or "USD",
                provider=SOURCE_USER_PHOTO_OCR,
                source_type=SOURCE_HTML,
                source_url=source_url,
            )
            items.append(pending_item)
            continue

        # No price on this line — likely a description wrapping from the
        # previous item (common for OCR'd multi-line menu descriptions).
        if pending_item is not None and len(line) > _MIN_NAME_LEN:
            pending_item.description = (
                f"{pending_item.description} {line}".strip()
                if pending_item.description
                else line
            )

    return items


def process_menu_photo(
    *,
    db: Session,
    image_id: str,
    place_id: str,
    image_url: str,
) -> int:
    """
    Runs OCR on an uploaded menu photo and feeds any extracted items into the
    normal menu ingestion pipeline. Best-effort — failures here must never
    affect the photo upload itself (see call site in image_processing_worker.py).

    Returns the number of items successfully ingested (0 on any failure).
    """
    raw_text = _get_vision_text(image_url)
    if not raw_text:
        logger.info("menu_ocr_no_text image_id=%s place_id=%s", image_id, place_id)
        return 0

    source_url = f"user_photo:{image_id}"

    items = parse_menu_photo_text(raw_text, source_url=source_url)
    if not items:
        logger.info(
            "menu_ocr_no_items_parsed image_id=%s place_id=%s text_len=%s",
            image_id, place_id, len(raw_text),
        )
        return 0

    # Register this as a menu source so it participates in the same
    # confidence/precedence system as scraped sources (menu_source_manager.py).
    # Confidence 0.6: below a verified POS provider (Toast/Square/etc.), above
    # generic scraped HTML — a real photo of the menu, but OCR + heuristic
    # parsing on it is imperfect.
    menu_source_manager.record_discovery(
        db=db,
        place_id=place_id,
        source_url=source_url,
        provider=SOURCE_USER_PHOTO_OCR,
        source_type="user_photo",
        confidence=0.6,
    )

    canonical_menu = ingest_menu_items(
        db=db,
        place_id=place_id,
        extracted_items=items,
        source_url=source_url,
    )

    if canonical_menu is None:
        menu_source_manager.record_failure(
            db=db, place_id=place_id, source_url=source_url,
            reason="ingest_produced_no_canonical_items",
        )
        db.commit()
        logger.info("menu_ocr_ingest_empty image_id=%s place_id=%s", image_id, place_id)
        return 0

    menu_source_manager.record_success(db=db, place_id=place_id, source_url=source_url)
    db.commit()

    logger.info(
        "menu_ocr_success image_id=%s place_id=%s items_parsed=%s",
        image_id, place_id, len(items),
    )
    return len(items)
