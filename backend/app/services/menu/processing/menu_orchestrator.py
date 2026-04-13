from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Any

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.menu.claims.menu_claim_emitter import emit_menu_claims
from app.services.menu.materialize_menu_truth import materialize_menu_truth
from app.services.menu.menu_pipeline import process_extracted_menu

from app.services.ingest.csv_ingest import run_ingest as run_csv_ingest

from app.services.menu.providers.grubhub_parser import parse_grubhub_payload
from app.services.menu.adapters.grubhub_adapter import adapt_grubhub_items

from app.services.menu.validation.validate_extracted_items import validate_extracted_items
from app.services.menu.validation.validate_normalized_items import validate_normalized_items

from app.services.menu.normalization.fingerprint import build_menu_fingerprint


logger = logging.getLogger(__name__)


MAX_TOTAL_EXTRACTED_ITEMS = 2000
MAX_ITEMS_PER_SOURCE = 1500
MIN_CANONICAL_ITEM_COUNT = 2


@dataclass(slots=True)
class MenuOrchestratorResult:
    place_id: str
    extracted_item_count: int = 0
    emitted_claim_count: int = 0
    materialized: bool = False
    source_count: int = 0


class MenuOrchestrator:

    def run_for_place(
        self,
        *,
        db: Session,
        place: Place,
    ) -> MenuOrchestratorResult:

        place_id = self._clean_str(getattr(place, "id", None))
        csv_path = self._clean_str(getattr(place, "menu_csv_path", None))
        grubhub_payload = getattr(place, "grubhub_payload", None)

        if not place_id:
            raise ValueError("place.id required")

        result = MenuOrchestratorResult(place_id=place_id)

        logger.info(
            "menu_orchestrator_start place_id=%s csv=%s grubhub=%s",
            place_id,
            bool(csv_path),
            bool(grubhub_payload),
        )

        extracted_items: List[Any] = []
        seen_items: Set[str] = set()
        sources_used = 0

        # =========================================================
        # GRUBHUB
        # =========================================================

        if grubhub_payload:
            try:
                raw_items = parse_grubhub_payload(grubhub_payload) or []
                gh_items = adapt_grubhub_items(raw_items) or []
                gh_items = validate_extracted_items(gh_items)

                accepted = 0

                for item in gh_items[:MAX_ITEMS_PER_SOURCE]:

                    if len(extracted_items) >= MAX_TOTAL_EXTRACTED_ITEMS:
                        break

                    key = self._item_key(item)
                    if not key or key in seen_items:
                        continue

                    seen_items.add(key)
                    extracted_items.append(item)
                    accepted += 1

                if accepted > 0:
                    sources_used += 1

                logger.info(
                    "grubhub_ingest_complete place_id=%s raw=%s accepted=%s",
                    place_id,
                    len(raw_items),
                    accepted,
                )

            except Exception as exc:
                logger.exception("grubhub_ingest_failed place_id=%s error=%s", place_id, exc)

        # =========================================================
        # CSV
        # =========================================================

        if csv_path:
            try:
                csv_items = run_csv_ingest(Path(csv_path)) or []

                accepted = 0

                for item in csv_items[:MAX_ITEMS_PER_SOURCE]:

                    if len(extracted_items) >= MAX_TOTAL_EXTRACTED_ITEMS:
                        break

                    key = self._item_key(item)
                    if not key or key in seen_items:
                        continue

                    seen_items.add(key)
                    extracted_items.append(item)
                    accepted += 1

                if accepted > 0:
                    sources_used += 1

                logger.info(
                    "csv_ingest_complete place_id=%s raw=%s accepted=%s",
                    place_id,
                    len(csv_items),
                    accepted,
                )

            except Exception as exc:
                logger.exception("csv_ingest_failed place_id=%s error=%s", place_id, exc)

        result.extracted_item_count = len(extracted_items)
        result.source_count = sources_used

        if not extracted_items:
            logger.info("menu_orchestrator_no_items place_id=%s", place_id)
            return result

        # =========================================================
        # PIPELINE
        # =========================================================

        try:
            canonical_menu = process_extracted_menu(extracted_items)
        except Exception as exc:
            logger.exception("pipeline_failed place_id=%s error=%s", place_id, exc)
            return result

        canonical_items = self._flatten_menu(canonical_menu)

        if len(canonical_items) < MIN_CANONICAL_ITEM_COUNT:
            logger.info("menu_orchestrator_rejected_low_quality place_id=%s", place_id)
            return result

        normalized_items = self._build_normalized_items(canonical_items)
        normalized_items = validate_normalized_items(normalized_items)

        if not normalized_items:
            logger.warning("normalized_items_empty place_id=%s", place_id)
            return result

        # =========================================================
        # CLAIMS
        # =========================================================

        try:
            claims = emit_menu_claims(
                db=db,
                place_id=place_id,
                items=normalized_items,
                source="menu_orchestrator",
                confidence=0.9,
                weight=1.0,
            )

            result.emitted_claim_count = len(claims or [])

        except Exception as exc:
            logger.exception("claim_emit_failed place_id=%s error=%s", place_id, exc)
            return result

        # =========================================================
        # MATERIALIZE
        # =========================================================

        try:
            menu = materialize_menu_truth(db=db, place_id=place_id)
            result.materialized = menu is not None
        except Exception as exc:
            logger.exception("materialize_failed place_id=%s error=%s", place_id, exc)

        logger.info(
            "menu_orchestrator_complete place_id=%s sources=%s extracted=%s claims=%s",
            place_id,
            result.source_count,
            result.extracted_item_count,
            result.emitted_claim_count,
        )

        return result

    # =========================================================
    # HELPERS
    # =========================================================

    def _flatten_menu(self, menu):
        items = []
        for section in getattr(menu, "sections", []) or []:
            section_name = self._clean_str(getattr(section, "name", None)) or "uncategorized"

            for item in getattr(section, "items", []) or []:
                if not getattr(item, "section", None):
                    item.section = section_name
                items.append(item)

        return items

    def _item_key(self, item) -> Optional[str]:
        name = self._get(item, "name")
        if not name:
            return None

        section = self._get(item, "section") or "uncategorized"
        currency = self._get(item, "currency") or "USD"

        return build_menu_fingerprint(
            name=name,
            section=section,
            currency=currency,
        )

    def _build_normalized_items(self, items):
        from app.services.menu.contracts import NormalizedMenuItem

        out: List[NormalizedMenuItem] = []
        seen: Set[str] = set()

        for item in items:
            name = self._get(item, "name")
            if not name:
                continue

            section = self._get(item, "section") or "uncategorized"
            currency = self._get(item, "currency") or "USD"
            description = self._get(item, "description")
            price_cents = self._get(item, "price_cents", raw=True)

            fingerprint = build_menu_fingerprint(
                name=name,
                section=section,
                currency=currency,
            )

            if fingerprint in seen:
                continue

            seen.add(fingerprint)

            out.append(
                NormalizedMenuItem(
                    name=name,
                    section=section,
                    description=description,
                    price_cents=price_cents,
                    currency=currency,
                    fingerprint=fingerprint,
                    source_url=None,
                )
            )

        return out

    def _get(self, item, field, *, raw: bool = False):
        if isinstance(item, dict):
            value = item.get(field)
        else:
            value = getattr(item, field, None)

        return value if raw else self._clean_str(value)

    def _clean_str(self, value: Optional[object]) -> Optional[str]:
        if value is None:
            return None
        try:
            s = str(value).strip()
            return s if s else None
        except Exception:
            return None