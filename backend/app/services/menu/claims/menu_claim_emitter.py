from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Set

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models.place_claim import PlaceClaim
from app.services.menu.claims.menu_claim_keys import build_menu_claim_key
from app.services.menu.claims.menu_claim_values import (
    build_menu_claim_payload,
    claim_payload_to_json,
)
from app.services.menu.contracts import NormalizedMenuItem


logger = logging.getLogger(__name__)


DEFAULT_CONFIDENCE = 0.8
DEFAULT_WEIGHT = 1.0
DEFAULT_SOURCE = "menu_extractor"

MAX_BATCH = 2000
MIN_ITEMS_TO_EMIT = 2


# =========================================================
# SAFE HELPERS
# =========================================================

def _safe_str(val: object) -> Optional[str]:
    try:
        if val is None:
            return None
        cleaned = str(val).strip()
        return cleaned or None
    except Exception:
        return None


def _safe_float(val: object, default: float) -> float:
    try:
        parsed = float(val)
        if parsed < 0:
            return default
        return parsed
    except Exception:
        return default


# =========================================================
# MAIN EMITTER
# =========================================================

def emit_menu_claims(
    *,
    db: Session,
    place_id: str,
    items: Iterable[NormalizedMenuItem],
    source_url: Optional[str] = None,
    source: str = DEFAULT_SOURCE,
    confidence: float = DEFAULT_CONFIDENCE,
    weight: float = DEFAULT_WEIGHT,
    is_verified_source: bool = False,
    is_user_submitted: bool = False,
) -> List[PlaceClaim]:

    if not place_id:
        logger.error("claims_missing_place_id")
        return []

    source = _safe_str(source) or DEFAULT_SOURCE
    source_url = _safe_str(source_url)
    confidence = _safe_float(confidence, DEFAULT_CONFIDENCE)
    weight = _safe_float(weight, DEFAULT_WEIGHT)

    items_list = list(items)

    if len(items_list) < MIN_ITEMS_TO_EMIT:
        logger.info(
            "claims_skipped_low_item_count place=%s count=%s",
            place_id,
            len(items_list),
        )
        return []

    emitted: List[PlaceClaim] = []
    batch_keys: Set[str] = set()

    total_attempted = 0
    skipped_duplicates = 0
    failed_items = 0

    for item in items_list:

        if total_attempted >= MAX_BATCH:
            logger.warning("claims_batch_limit_hit place=%s", place_id)
            break

        total_attempted += 1

        try:
            fingerprint = _safe_str(getattr(item, "fingerprint", None))
            name = _safe_str(getattr(item, "name", None))

            if not fingerprint or not name:
                failed_items += 1
                continue

            # 🔥 HARDEN fingerprint (defensive)
            fingerprint = fingerprint.strip().lower()

            # =========================================================
            # CLAIM KEY
            # =========================================================

            claim_key = build_menu_claim_key(
                fingerprint=fingerprint,
                source_url=source_url,
            )

            if not claim_key:
                failed_items += 1
                continue

            # 🔥 batch-level dedupe
            if claim_key in batch_keys:
                skipped_duplicates += 1
                continue

            # =========================================================
            # PAYLOAD
            # =========================================================

            payload = build_menu_claim_payload(
                item=item,
                source_url=source_url,
            )

            payload_json = claim_payload_to_json(payload)

            if not isinstance(payload_json, dict):
                failed_items += 1
                continue

            if not _safe_str(payload_json.get("name")):
                failed_items += 1
                continue

            # =========================================================
            # CREATE CLAIM
            # =========================================================

            claim = PlaceClaim(
                place_id=place_id,
                field="menu_item",
                claim_key=claim_key,
                value_json=payload_json,
                source=source,
                confidence=confidence,
                weight=weight,
                is_verified_source=bool(is_verified_source),
                is_user_submitted=bool(is_user_submitted),
            )

            db.add(claim)
            emitted.append(claim)
            batch_keys.add(claim_key)

        except Exception as exc:
            failed_items += 1
            logger.warning(
                "claim_failed place=%s item=%s error=%s",
                place_id,
                getattr(item, "name", None),
                exc,
            )

    # =========================================================
    # FLUSH (PROD SAFE)
    # =========================================================

    try:
        if emitted:
            db.flush()

            logger.info(
                "claims_post_flush place=%s emitted=%s",
                place_id,
                len(emitted),
            )
        else:
            logger.warning(
                "claims_zero_emitted place=%s attempted=%s skipped=%s failed=%s",
                place_id,
                total_attempted,
                skipped_duplicates,
                failed_items,
            )

    except IntegrityError as exc:
        db.rollback()

        logger.warning(
            "claims_integrity_error place=%s error=%s",
            place_id,
            exc,
        )

        # 🔥 DO NOT kill pipeline — return partial success
        return emitted

    except Exception as exc:
        db.rollback()
        logger.exception("claim_flush_failed place=%s error=%s", place_id, exc)
        return []

    logger.info(
        "claims_done place=%s emitted=%s attempted=%s skipped=%s failed=%s",
        place_id,
        len(emitted),
        total_attempted,
        skipped_duplicates,
        failed_items,
    )

    return emitted