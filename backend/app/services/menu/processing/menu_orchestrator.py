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
from app.services.menu.menu_publisher import MenuPublisher

from app.services.ingest.csv_ingest import run_ingest as run_csv_ingest

from app.services.menu.providers.grubhub_parser import parse_grubhub_payload
from app.services.menu.adapters.grubhub_adapter import adapt_grubhub_items

from app.services.menu.validation.validate_extracted_items import validate_extracted_items
from app.services.menu.validation.validate_normalized_items import validate_normalized_items

from app.services.menu.normalization.fingerprint import build_menu_fingerprint
from app.services.images.menu_image_bridge import MenuImageBridge

from app.services.menu.extraction.fetch_html import fetch_html
from app.services.menu.extraction.js.js_provider_router import route_provider
from app.services.menu.extraction.provider.provider_detector import detect_provider
from app.services.menu.extraction.html_menu_extractor import extract_html_menu
from app.services.menu.discovery.menu_source_manager import menu_source_manager
from app.services.menu.source_quality import best_usable_source, normalize_http_source


logger = logging.getLogger(__name__)


MAX_TOTAL_EXTRACTED_ITEMS = 2000
MAX_ITEMS_PER_SOURCE = 1500
MIN_CANONICAL_ITEM_COUNT = 2

# Provider confidence hierarchy — used for claim emission weighting.
# Lower-confidence sources cannot overwrite higher-confidence truth.
PROVIDER_CONFIDENCE: dict[str, float] = {
    "toast":       0.97,
    "popmenu":     0.93,
    "square":      0.92,
    "chownow":     0.91,
    "clover":      0.88,
    "grubhub":     0.80,
    "html":        0.50,
    "jsonld":      0.65,
    "hydration":   0.75,
    "fallback":    0.35,
    "aggregator":  0.30,
}
DEFAULT_CONFIDENCE = 0.70


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

        # Live-fetch Grubhub payload when not pre-loaded but URL is present
        if not grubhub_payload:
            _gh_url = normalize_http_source(getattr(place, "grubhub_url", None))
            _website = normalize_http_source(getattr(place, "website", None))
            _candidate = _gh_url or _website
            if _candidate and "grubhub.com" in _candidate:
                try:
                    from app.services.menu.fetchers.grubhub_fetcher import fetch_grubhub_menu
                    grubhub_payload = fetch_grubhub_menu(place)
                    if grubhub_payload:
                        logger.info(
                            "menu_orchestrator.grubhub_live_fetch_ok place_id=%s",
                            place_id,
                        )
                    else:
                        logger.debug(
                            "menu_orchestrator.grubhub_live_fetch_empty place_id=%s",
                            place_id,
                        )
                except Exception as exc:
                    logger.debug(
                        "menu_orchestrator.grubhub_live_fetch_failed place_id=%s error=%s",
                        place_id,
                        exc,
                    )

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

        # =========================================================
        # PROVIDER EXTRACTION (Toast, Clover, Square, ChowNow, PopMenu)
        # =========================================================

        # Source probe order:
        #   1. Best active MenuSource URL (highest confidence, lineage-tracked)
        #   2. place.menu_source_url (denormalized pointer, may lag by one cycle)
        #   3. place.website (raw site, no provider detection yet)
        menu_source_url = getattr(place, "menu_source_url", None)
        website = getattr(place, "website", None)
        _best_known = menu_source_manager.get_best_source_url(db=db, place_id=place_id)
        _probe_url = best_usable_source(_best_known, menu_source_url, website)

        if _probe_url and not extracted_items:
            _html: str | None = None

            # ── Negative URL cache check — skip confirmed dead/blocked URLs ──
            # Only set after permanent failures (4xx, blocked HTML, captcha).
            # Transient failures (timeout) use shorter TTL and don't block forever.
            _neg_hit = self._check_negative_cache(_probe_url)
            if _neg_hit:
                logger.debug(
                    "menu_orchestrator.negative_cache_hit place_id=%s url=%s reason=%s",
                    place_id,
                    _probe_url,
                    _neg_hit,
                )
            else:
                try:
                    _html = fetch_html(_probe_url)
                except Exception as exc:
                    menu_source_manager.record_failure(
                        db=db, place_id=place_id, source_url=_probe_url,
                        reason=f"fetch_error:{type(exc).__name__}",
                    )
                    self._set_negative_cache(_probe_url, exc)
                    logger.debug(
                        "menu_orchestrator.website_fetch_failed place_id=%s url=%s error=%s",
                        place_id,
                        _probe_url,
                        exc,
                    )

            if _html:
                # -- known provider path --
                try:
                    _provider = detect_provider(_html, _probe_url)

                    if _provider:
                        logger.info(
                            "menu_orchestrator.provider_detected place_id=%s provider=%s",
                            place_id,
                            _provider,
                        )

                        provider_items = route_provider(_html, _probe_url) or []
                        provider_items = validate_extracted_items(provider_items)

                        accepted = 0

                        for item in provider_items[:MAX_ITEMS_PER_SOURCE]:
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
                            menu_source_manager.record_discovery(
                                db=db,
                                place_id=place_id,
                                source_url=_probe_url,
                                provider=_provider,
                                source_type="provider",
                                confidence=PROVIDER_CONFIDENCE.get(
                                    (_provider or "").lower(), DEFAULT_CONFIDENCE
                                ),
                            )
                            menu_source_manager.record_success(
                                db=db, place_id=place_id, source_url=_probe_url
                            )

                        logger.info(
                            "menu_orchestrator.provider_complete place_id=%s provider=%s accepted=%s",
                            place_id,
                            _provider,
                            accepted,
                        )

                except Exception as exc:
                    logger.debug(
                        "menu_orchestrator.provider_extraction_failed place_id=%s error=%s",
                        place_id,
                        exc,
                    )

                # -- Hydration fallback (JS-embedded state — __NEXT_DATA__, __NUXT__, etc.) --
                if not extracted_items:
                    try:
                        from app.services.menu.extraction.hydration_menu_extractor import (
                            extract_hydration_menu,
                        )
                        hydration_items = extract_hydration_menu(_html, url=_probe_url) or []
                        hydration_items = validate_extracted_items(hydration_items)

                        accepted = 0

                        for item in hydration_items[:MAX_ITEMS_PER_SOURCE]:
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
                            menu_source_manager.record_discovery(
                                db=db,
                                place_id=place_id,
                                source_url=_probe_url,
                                provider="hydration",
                                source_type="hydration",
                                confidence=PROVIDER_CONFIDENCE.get("hydration", DEFAULT_CONFIDENCE),
                            )
                            menu_source_manager.record_success(
                                db=db, place_id=place_id, source_url=_probe_url
                            )
                            logger.info(
                                "menu_orchestrator.hydration_complete place_id=%s accepted=%s",
                                place_id,
                                accepted,
                            )

                    except Exception as exc:
                        logger.debug(
                            "menu_orchestrator.hydration_failed place_id=%s error=%s",
                            place_id,
                            exc,
                        )

                # -- HTML heuristic fallback (no known provider, or provider yielded 0 items) --
                if not extracted_items:
                    try:
                        html_items = extract_html_menu(_html, source_url=_probe_url) or []
                        html_items = validate_extracted_items(html_items)

                        accepted = 0

                        for item in html_items[:MAX_ITEMS_PER_SOURCE]:
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
                            menu_source_manager.record_discovery(
                                db=db,
                                place_id=place_id,
                                source_url=_probe_url,
                                provider="html",
                                source_type="html",
                                confidence=PROVIDER_CONFIDENCE.get("html", DEFAULT_CONFIDENCE),
                            )
                            menu_source_manager.record_success(
                                db=db, place_id=place_id, source_url=_probe_url
                            )
                        else:
                            menu_source_manager.record_failure(
                                db=db, place_id=place_id, source_url=_probe_url,
                                reason="html_zero_items",
                            )

                        logger.info(
                            "menu_orchestrator.html_fallback_complete place_id=%s accepted=%s",
                            place_id,
                            accepted,
                        )

                    except Exception as exc:
                        menu_source_manager.record_failure(
                            db=db, place_id=place_id, source_url=_probe_url,
                            reason=f"html_fallback_exception:{type(exc).__name__}",
                        )
                        logger.debug(
                            "menu_orchestrator.html_fallback_failed place_id=%s error=%s",
                            place_id,
                            exc,
                        )

        # =========================================================
        # ADVANCED ESCALATION (PDF, JSON-LD, JS state, GraphQL/API
        # discovery, iframe menus, headless-browser rendering)
        # =========================================================
        # Everything above tries only: known-provider parsing, one HTML
        # fetch, hydration state, and a heuristic HTML parser. It misses PDF
        # menus, sites whose menu lives behind a GraphQL/JSON API, menus
        # embedded in an iframe, and pages that render nothing without JS.
        # menu_extraction_router.extract_menu handles all of those, plus a
        # real headless-browser fallback — but only runs here when every
        # cheaper method above found zero items, so places that already
        # work are completely unaffected.
        if not extracted_items and _probe_url:
            try:
                from app.services.menu.menu_extraction_router import (
                    extract_menu as _extract_menu_advanced,
                )

                escalated_items = _extract_menu_advanced(
                    html=_html or "",
                    url=_probe_url,
                    place_id=place_id,
                ) or []
                escalated_items = validate_extracted_items(escalated_items)

                accepted = 0
                for item in escalated_items[:MAX_ITEMS_PER_SOURCE]:
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
                    menu_source_manager.record_success(
                        db=db, place_id=place_id, source_url=_probe_url
                    )

                logger.info(
                    "menu_orchestrator.advanced_escalation_complete place_id=%s accepted=%s",
                    place_id,
                    accepted,
                )

            except Exception as exc:
                logger.debug(
                    "menu_orchestrator.advanced_escalation_failed place_id=%s error=%s",
                    place_id,
                    exc,
                )

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

        # Derive confidence from the provider detected during extraction.
        # Falls back to DEFAULT_CONFIDENCE when provider is unknown.
        _source_provider = None
        if extracted_items:
            _source_provider = getattr(extracted_items[0], "provider", None)
        _confidence = PROVIDER_CONFIDENCE.get(
            (_source_provider or "").lower(), DEFAULT_CONFIDENCE
        )

        try:
            claims = emit_menu_claims(
                db=db,
                place_id=place_id,
                items=normalized_items,
                source=f"menu_orchestrator:{_source_provider or 'unknown'}",
                confidence=_confidence,
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

        # =========================================================
        # PUBLISH — write to menu_items cache
        # =========================================================

        if result.materialized:
            try:
                publisher = MenuPublisher()
                publisher.publish(place_id=place_id, db=db)
            except Exception as exc:
                logger.warning(
                    "menu_orchestrator.publish_failed place_id=%s error=%s",
                    place_id,
                    exc,
                )

        # =========================================================
        # ITEM IMAGE BRIDGE — Phase 3 compliant
        # Collect image_url from extracted items → classify → score
        # → visibility assign → write to place_images → re-elect primary.
        # =========================================================

        item_image_urls = [
            item.image_url
            for item in extracted_items
            if getattr(item, "image_url", None)
        ]

        if item_image_urls:
            try:
                provider = (
                    extracted_items[0].provider
                    if extracted_items and getattr(extracted_items[0], "provider", None)
                    else "menu_item"
                )
                bridge = MenuImageBridge()
                bridge_result = bridge.ingest(
                    db=db,
                    place_id=place_id,
                    image_urls=item_image_urls,
                    source=f"{provider}_item",
                )
                logger.info(
                    "menu_orchestrator.image_bridge place_id=%s %s",
                    place_id,
                    bridge_result,
                )
            except Exception as exc:
                logger.exception(
                    "menu_orchestrator.image_bridge_failed place_id=%s error=%s",
                    place_id,
                    exc,
                )

        logger.info(
            "menu_orchestrator_complete place_id=%s sources=%s extracted=%s claims=%s",
            place_id,
            result.source_count,
            result.extracted_item_count,
            result.emitted_claim_count,
        )

        return result

    # =========================================================
    # PIPELINE RUNNER (pre-extracted items path)
    # =========================================================

    def run_with_items(
        self,
        *,
        db: Session,
        place_id: str,
        items: list,
        source: str = "extraction_controller",
    ) -> "MenuOrchestratorResult":
        """
        Run the claims → materialize → publish → image-bridge pipeline
        for a pre-extracted list of ExtractedMenuItem objects.

        Used by MasterDataOrchestrator when ExtractionController produces items.
        """
        result = MenuOrchestratorResult(place_id=place_id)

        if not items:
            return result

        # Validate
        validated = validate_extracted_items(items)
        result.extracted_item_count = len(validated)
        result.source_count = 1 if validated else 0

        if not validated:
            logger.info("run_with_items_no_valid place_id=%s", place_id)
            return result

        # ── PIPELINE ─────────────────────────────────────────────────
        try:
            canonical_menu = process_extracted_menu(validated)
        except Exception as exc:
            logger.exception(
                "run_with_items.pipeline_failed place_id=%s error=%s", place_id, exc
            )
            return result

        canonical_items = self._flatten_menu(canonical_menu)

        if len(canonical_items) < MIN_CANONICAL_ITEM_COUNT:
            logger.info(
                "run_with_items_rejected_low_quality place_id=%s count=%s",
                place_id, len(canonical_items),
            )
            return result

        normalized_items = self._build_normalized_items(canonical_items)
        normalized_items = validate_normalized_items(normalized_items)

        if not normalized_items:
            logger.warning("run_with_items_normalized_empty place_id=%s", place_id)
            return result

        # ── CLAIMS ───────────────────────────────────────────────────
        # Derive confidence from items' provider field (set by extractors).
        _item_provider = None
        if validated:
            _item_provider = getattr(validated[0], "provider", None)
        _item_confidence = PROVIDER_CONFIDENCE.get(
            (_item_provider or "").lower(), DEFAULT_CONFIDENCE
        )

        try:
            claims = emit_menu_claims(
                db=db,
                place_id=place_id,
                items=normalized_items,
                source=source,
                confidence=_item_confidence,
                weight=1.0,
            )
            result.emitted_claim_count = len(claims or [])
        except Exception as exc:
            logger.exception(
                "run_with_items.claim_emit_failed place_id=%s error=%s", place_id, exc
            )
            return result

        # ── MATERIALIZE ───────────────────────────────────────────────
        try:
            menu = materialize_menu_truth(db=db, place_id=place_id)
            result.materialized = menu is not None
        except Exception as exc:
            logger.exception(
                "run_with_items.materialize_failed place_id=%s error=%s", place_id, exc
            )

        # ── PUBLISH ───────────────────────────────────────────────────
        if result.materialized:
            try:
                publisher = MenuPublisher()
                publisher.publish(place_id=place_id, db=db)
            except Exception as exc:
                logger.warning(
                    "run_with_items.publish_failed place_id=%s error=%s", place_id, exc
                )

        # ── ITEM IMAGE BRIDGE ─────────────────────────────────────────
        item_image_urls = [
            item.image_url
            for item in validated
            if getattr(item, "image_url", None)
        ]

        if item_image_urls:
            try:
                from app.services.images.menu_image_bridge import MenuImageBridge
                bridge = MenuImageBridge()
                bridge_result = bridge.ingest(
                    db=db,
                    place_id=place_id,
                    image_urls=item_image_urls,
                    source=f"{source}_item",
                )
                logger.info(
                    "run_with_items.image_bridge place_id=%s %s",
                    place_id, bridge_result,
                )
            except Exception as exc:
                logger.exception(
                    "run_with_items.image_bridge_failed place_id=%s error=%s",
                    place_id, exc,
                )

        logger.info(
            "run_with_items_complete place_id=%s extracted=%s claims=%s materialized=%s",
            place_id,
            result.extracted_item_count,
            result.emitted_claim_count,
            result.materialized,
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
                    image_url=self._get(item, "image_url"),
                    provider=self._get(item, "provider"),
                    source_type=self._get(item, "source_type"),
                    source_url=self._get(item, "source_url"),
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

    # =========================================================
    # NEGATIVE CACHE — URL-level, prevents re-fetching dead/blocked URLs
    # =========================================================

    def _check_negative_cache(self, url: str) -> Optional[str]:
        """
        Return the cached failure reason if this URL is negative-cached, else None.
        Never raises.
        """
        try:
            from app.services.cache.cache_keys import provider_probe_negative_key
            from app.services.cache.response_cache import response_cache
            return response_cache.get(provider_probe_negative_key(url=url))
        except Exception:
            return None

    def _set_negative_cache(self, url: str, exc: Exception) -> None:
        """
        Cache a URL as negative (blocked/dead) with TTL based on failure type.

        TTL rules:
        - Permanent (4xx HTTP, blocked HTML, captcha): 12 h
        - Transient (timeout): 30 min
        - Other: 1 h

        Never caches 'html_zero_items' — site is reachable, just has no menu.
        Never raises.
        """
        try:
            from app.services.cache.cache_keys import provider_probe_negative_key
            from app.services.cache.cache_ttl import (
                NEGATIVE_PROBE_TTL_BLOCKED,
                NEGATIVE_PROBE_TTL_DEFAULT,
                NEGATIVE_PROBE_TTL_TIMEOUT,
            )
            from app.services.cache.response_cache import response_cache

            reason = str(exc)

            # Determine TTL by failure type
            if any(token in reason for token in ("status=4", "blocked_html", "captcha", "hard_403")):
                ttl = NEGATIVE_PROBE_TTL_BLOCKED
            elif any(token in reason for token in ("timeout", "Timeout", "fetch_timeout")):
                ttl = NEGATIVE_PROBE_TTL_TIMEOUT
            else:
                ttl = NEGATIVE_PROBE_TTL_DEFAULT

            key = provider_probe_negative_key(url=url)
            response_cache.set(key, reason, ttl_seconds=ttl)

        except Exception:
            pass  # negative cache is best-effort — never crash extraction
