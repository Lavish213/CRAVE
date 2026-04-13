from __future__ import annotations

from typing import Iterable, List, Optional
import logging

from sqlalchemy.orm import Session

from app.services.menu.contracts import ExtractedMenuItem, NormalizedMenuItem
from app.services.menu.orchestration.menu_item_normalizer import normalize_menu_items
from app.services.menu.claims.menu_claim_emitter import emit_menu_claims
from app.services.menu.materialize_menu_truth import materialize_menu_truth


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500


# ---------------------------------------------------------
# Normalization
# ---------------------------------------------------------

def normalize_items(
    extracted_items: List[ExtractedMenuItem],
) -> List[NormalizedMenuItem]:

    try:
        normalized = normalize_menu_items(extracted_items)
    except Exception as exc:
        logger.exception("menu_normalization_failed error=%s", exc)
        return []

    if len(normalized) > MAX_ITEMS:
        normalized = normalized[:MAX_ITEMS]

    return normalized


# ---------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------

def ingest_menu_items(
    *,
    db: Session,
    place_id: str,
    extracted_items: Iterable[ExtractedMenuItem],
    source_url: Optional[str] = None,
):

    if not db or not place_id or not extracted_items:
        logger.warning(
            "menu_ingest_invalid_input place=%s",
            place_id,
        )
        return None

    # 🔥 FIX: convert ONCE (prevents generator exhaustion)
    extracted_list = list(extracted_items)

    if not extracted_list:
        logger.info("menu_ingest_no_input_items place=%s", place_id)
        return None

    # ---------------------------------------------------------
    # Normalize
    # ---------------------------------------------------------

    normalized_items = normalize_items(extracted_list)

    if not normalized_items:
        logger.info("menu_ingest_no_valid_items place=%s", place_id)
        return None

    # ---------------------------------------------------------
    # Emit claims
    # ---------------------------------------------------------

    try:
        emitted = emit_menu_claims(
            db=db,
            place_id=place_id,
            items=normalized_items,
            source_url=source_url,
        )

        emitted_count = len(emitted or [])

    except Exception as exc:
        logger.exception(
            "menu_claim_emit_failed place=%s error=%s",
            place_id,
            exc,
        )
        return None

    # ---------------------------------------------------------
    # Materialize truth
    # ---------------------------------------------------------

    try:
        canonical_menu = materialize_menu_truth(
            db=db,
            place_id=place_id,
        )

    except Exception as exc:
        logger.exception(
            "menu_materialize_failed place=%s error=%s",
            place_id,
            exc,
        )
        return None

    # ---------------------------------------------------------
    # Final log
    # ---------------------------------------------------------

    logger.info(
        "menu_ingest_success place=%s extracted=%s normalized=%s emitted=%s",
        place_id,
        len(extracted_list),
        len(normalized_items),
        emitted_count,
    )

    return canonical_menu