"""
MasterDataOrchestrator — Phase C

Ensures DB completeness for a place automatically.

For each place:
    MENU:
        if menu_items == 0: run ExtractionController
        elif menu_items < threshold: try fallback extractor
        → emit_menu_claims → materialize_menu_truth → MenuPublisher

    IMAGES:
        if images == 0: run image ingestion
        elif images weak: run enrichment
        → Phase 3 pipeline (classify → score → visibility → primary)
        → item images from menu go through MenuImageBridge

    FALLBACK:
        Google used ONLY if no extractor works

Rules (enforced):
    - NEVER writes fake data
    - NEVER bypasses Phase 3 for images
    - NEVER uses Google as primary source
    - NEVER overrides provider data with Google data
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.menu_item import MenuItem
from app.db.models.place_image import PlaceImage

from app.services.menu.extraction_controller import ExtractionController, ExtractionControllerResult
from app.services.menu.processing.menu_orchestrator import MenuOrchestrator, PROVIDER_CONFIDENCE, DEFAULT_CONFIDENCE
from app.services.menu.menu_publisher import MenuPublisher
from app.services.images.menu_image_bridge import MenuImageBridge
from app.services.menu.fetch.fetch_strategy_router import (
    classify_fetch_strategy,
    STRATEGY_FAIL_FAST,
)
from app.services.menu.discovery.menu_source_manager import menu_source_manager


logger = logging.getLogger(__name__)


# =========================================================
# THRESHOLDS
# =========================================================

# Below this count → try fallback extractor
MENU_ITEMS_LOW_THRESHOLD = 3

# Below this count → try image enrichment
IMAGES_WEAK_THRESHOLD = 2

# Minimum quality_score to consider image "strong"
IMAGE_QUALITY_STRONG = 0.50


# =========================================================
# RESULT
# =========================================================

@dataclass(slots=True)
class MasterDataResult:
    place_id: str

    # Menu
    menu_action: str = "none"        # "extracted", "fallback", "skipped", "failed"
    menu_items_before: int = 0
    menu_items_after: int = 0
    menu_provider: Optional[str] = None
    menu_fallback_used: bool = False

    # Images
    image_action: str = "none"       # "ingested", "enriched", "skipped", "failed"
    images_before: int = 0
    images_after: int = 0
    item_images_bridged: int = 0

    # Access diagnostics (populated by strategy router)
    menu_strategy: Optional[str] = None        # strategy used
    menu_blocked_reason: Optional[str] = None  # why skipped if fail_fast
    menu_needs_auth: bool = False
    menu_needs_browser: bool = False
    menu_access_failure: bool = False    # blocked before extraction ran
    menu_extraction_failure: bool = False  # fetch ok but 0 items

    # Typed failure reason (one of FAILURE_* from extraction_controller)
    failure_reason: Optional[str] = None

    # URL actually used for extraction (may differ from place.website)
    source_selected: Optional[str] = None

    # Errors
    errors: List[str] = field(default_factory=list)


# =========================================================
# ORCHESTRATOR
# =========================================================

class MasterDataOrchestrator:
    """
    Ensures a place has complete menu and image data.

    Usage:
        mdo = MasterDataOrchestrator()
        result = mdo.ensure_place(db=db, place=place)
    """

    def __init__(self) -> None:
        self._extractor = ExtractionController()
        self._menu_orchestrator = MenuOrchestrator()
        self._publisher = MenuPublisher()
        self._image_bridge = MenuImageBridge()

    def ensure_place(
        self,
        *,
        db: Session,
        place: Place,
    ) -> MasterDataResult:

        place_id = str(getattr(place, "id", "") or "")

        if not place_id:
            raise ValueError("place.id required")

        result = MasterDataResult(place_id=place_id)

        # ── Snapshot current state ────────────────────────────────────
        result.menu_items_before = self._count_menu_items(db, place_id)
        result.images_before = self._count_images(db, place_id)

        logger.info(
            "master_data_orchestrator.start place_id=%s menu_before=%s images_before=%s",
            place_id,
            result.menu_items_before,
            result.images_before,
        )

        # ── MENU ─────────────────────────────────────────────────────
        self._handle_menu(db=db, place=place, result=result)

        # ── IMAGES ───────────────────────────────────────────────────
        self._handle_images(db=db, place=place, result=result)

        # ── Final counts ─────────────────────────────────────────────
        result.menu_items_after = self._count_menu_items(db, place_id)
        result.images_after = self._count_images(db, place_id)

        logger.info(
            "master_data_orchestrator.complete place_id=%s "
            "menu_action=%s menu_after=%s "
            "image_action=%s images_after=%s",
            place_id,
            result.menu_action,
            result.menu_items_after,
            result.image_action,
            result.images_after,
        )

        return result

    # =========================================================
    # MENU HANDLING
    # =========================================================

    def _handle_menu(
        self,
        *,
        db: Session,
        place: Place,
        result: MasterDataResult,
    ) -> None:

        place_id = result.place_id

        if result.menu_items_before == 0:
            # No menu at all — run full extraction
            self._run_menu_extraction(db=db, place=place, result=result, is_fallback=False)

        elif result.menu_items_before < MENU_ITEMS_LOW_THRESHOLD:
            # Weak menu — try extraction again as fallback
            logger.info(
                "master_data_orchestrator.menu_low place_id=%s count=%s threshold=%s",
                place_id,
                result.menu_items_before,
                MENU_ITEMS_LOW_THRESHOLD,
            )
            self._run_menu_extraction(db=db, place=place, result=result, is_fallback=True)

        else:
            result.menu_action = "skipped"
            logger.info(
                "master_data_orchestrator.menu_skip place_id=%s count=%s",
                place_id,
                result.menu_items_before,
            )

    def _run_menu_extraction(
        self,
        *,
        db: Session,
        place: Place,
        result: MasterDataResult,
        is_fallback: bool,
    ) -> None:
        """
        PHASE 5 WIRED PATH:
        MasterDataOrchestrator → ExtractionController → pipeline

        Grubhub/CSV sources still routed through MenuOrchestrator directly
        (they have pre-loaded payloads; ExtractionController handles web/provider).
        """
        from app.services.menu.extraction_controller import (
            FAILURE_MISSING_AUTH, FAILURE_BLOCKED_PROVIDER,
        )

        place_id = result.place_id
        menu_source_url = str(getattr(place, "menu_source_url", "") or "").strip()
        website = str(getattr(place, "website", "") or "").strip()
        grubhub_url = str(getattr(place, "grubhub_url", "") or "").strip()
        # Prefer verified provider URL from discovery; grubhub last resort
        source_url = menu_source_url or website or grubhub_url

        # ── No URL at all → skip ──────────────────────────────────────
        if not source_url:
            result.menu_action = "failed"
            result.failure_reason = "no_website"
            result.errors.append("menu_extraction: no website or grubhub_url")
            return

        # ── Grubhub path: check auth, then use MenuOrchestrator ───────
        is_grubhub = "grubhub.com" in source_url
        if is_grubhub:
            strategy = classify_fetch_strategy(source_url)
            result.menu_strategy = strategy.strategy
            result.menu_needs_auth = strategy.needs_auth

            if strategy.strategy == STRATEGY_FAIL_FAST:
                result.menu_action = "failed"
                result.menu_blocked_reason = strategy.blocked_reason
                result.menu_access_failure = True
                result.failure_reason = FAILURE_MISSING_AUTH
                result.errors.append(
                    f"menu_extraction: access_blocked:{strategy.blocked_reason}"
                )
                logger.info(
                    "master_data_orchestrator.grubhub_blocked place_id=%s reason=%s",
                    place_id, strategy.blocked_reason,
                )
                return

            # Auth present — run MenuOrchestrator (handles grubhub live fetch)
            try:
                orch_result = self._menu_orchestrator.run_for_place(db=db, place=place)
                if orch_result.extracted_item_count >= 2:
                    result.menu_action = "fallback" if is_fallback else "extracted"
                    result.source_selected = source_url
                    menu_source_manager.record_discovery(
                        db=db,
                        place_id=place_id,
                        source_url=source_url,
                        provider="grubhub",
                        source_type="aggregator",
                        confidence=PROVIDER_CONFIDENCE.get("grubhub", DEFAULT_CONFIDENCE),
                    )
                    menu_source_manager.record_success(
                        db=db, place_id=place_id, source_url=source_url
                    )
                    try:
                        place.has_menu = True
                        db.flush()
                    except Exception:
                        pass
                    logger.info(
                        "master_data_orchestrator.grubhub_done place_id=%s items=%s",
                        place_id, orch_result.extracted_item_count,
                    )
                else:
                    menu_source_manager.record_failure(
                        db=db, place_id=place_id, source_url=source_url,
                        reason="success_zero_items",
                    )
                    result.menu_action = "failed"
                    result.menu_extraction_failure = True
                    result.failure_reason = "success_zero_items"
                    result.errors.append("menu_extraction: 0 items from grubhub")
            except Exception as exc:
                menu_source_manager.record_failure(
                    db=db, place_id=place_id, source_url=source_url,
                    reason=f"grubhub_exception:{type(exc).__name__}",
                )
                result.menu_action = "failed"
                result.failure_reason = "provider_bug"
                result.errors.append(f"menu_extraction: grubhub_exception:{exc}")
                logger.exception(
                    "master_data_orchestrator.grubhub_exception place_id=%s error=%s",
                    place_id, exc,
                )
            return

        # ── Web / Provider path: ExtractionController ─────────────────
        # Pre-flight strategy check
        strategy = classify_fetch_strategy(source_url)
        result.menu_strategy = strategy.strategy
        result.menu_needs_auth = strategy.needs_auth
        result.menu_needs_browser = strategy.needs_browser

        if strategy.strategy == STRATEGY_FAIL_FAST:
            result.menu_action = "failed"
            result.menu_blocked_reason = strategy.blocked_reason
            result.menu_access_failure = True
            result.failure_reason = strategy.blocked_reason or "fail_fast"
            result.errors.append(
                f"menu_extraction: access_blocked:{strategy.blocked_reason}"
            )
            logger.info(
                "master_data_orchestrator.menu_blocked place_id=%s reason=%s",
                place_id, strategy.blocked_reason,
            )
            return

        # Call ExtractionController — strategy-aware, Playwright-capable, menu-discovery
        try:
            ec_result = self._extractor.extract_for_place(place)

            result.menu_strategy = ec_result.strategy_used or result.menu_strategy
            result.failure_reason = ec_result.failure_reason
            result.source_selected = ec_result.selected_url

            if ec_result.access_failure:
                menu_source_manager.record_failure(
                    db=db, place_id=place_id, source_url=source_url,
                    reason=f"access_blocked:{ec_result.blocked_reason or ec_result.failure_reason}",
                )
                result.menu_action = "failed"
                result.menu_access_failure = True
                result.menu_blocked_reason = ec_result.blocked_reason
                result.errors.append(
                    f"menu_extraction: access_failure:{ec_result.error}"
                )
                logger.info(
                    "master_data_orchestrator.ec_access_failure place_id=%s "
                    "reason=%s failure_reason=%s",
                    place_id, ec_result.error, ec_result.failure_reason,
                )
                return

            if not ec_result.success:
                menu_source_manager.record_failure(
                    db=db, place_id=place_id, source_url=source_url,
                    reason=ec_result.failure_reason or "ec_no_items",
                )
                result.menu_action = "failed"
                result.menu_extraction_failure = True
                result.errors.append(
                    f"menu_extraction: ec_failed:{ec_result.failure_reason}"
                )
                logger.info(
                    "master_data_orchestrator.ec_no_items place_id=%s failure=%s",
                    place_id, ec_result.failure_reason,
                )
                return

            # Items extracted — run pipeline
            _ec_url = ec_result.selected_url or source_url
            pipe_result = self._menu_orchestrator.run_with_items(
                db=db,
                place_id=place_id,
                items=ec_result.items,
                source=f"ec_{ec_result.provider or ec_result.method or 'web'}",
            )

            if pipe_result.extracted_item_count >= 2:
                _ec_provider = (ec_result.provider or "").lower()
                menu_source_manager.record_discovery(
                    db=db,
                    place_id=place_id,
                    source_url=_ec_url,
                    provider=_ec_provider or None,
                    source_type="provider" if _ec_provider else "html",
                    confidence=PROVIDER_CONFIDENCE.get(_ec_provider, DEFAULT_CONFIDENCE),
                )
                menu_source_manager.record_success(
                    db=db, place_id=place_id, source_url=_ec_url
                )
                result.menu_action = "fallback" if is_fallback else "extracted"
                result.menu_provider = ec_result.provider
                result.menu_fallback_used = ec_result.fallback_used
                # Set has_menu flag — publisher doesn't do this
                try:
                    place.has_menu = True
                    db.flush()
                except Exception:
                    pass
                logger.info(
                    "master_data_orchestrator.menu_done place_id=%s items=%s "
                    "strategy=%s selected_url=%s",
                    place_id,
                    pipe_result.extracted_item_count,
                    result.menu_strategy,
                    result.source_selected,
                )
            else:
                menu_source_manager.record_failure(
                    db=db, place_id=place_id, source_url=_ec_url,
                    reason="pipeline_rejected_items",
                )
                result.menu_action = "failed"
                result.menu_extraction_failure = True
                result.failure_reason = "success_zero_items"
                result.errors.append(
                    "menu_extraction: pipeline_rejected_items"
                )

        except Exception as exc:
            menu_source_manager.record_failure(
                db=db, place_id=place_id, source_url=source_url,
                reason=f"exception:{type(exc).__name__}",
            )
            result.menu_action = "failed"
            result.failure_reason = "provider_bug"
            result.errors.append(f"menu_extraction: exception:{exc}")
            logger.exception(
                "master_data_orchestrator.menu_exception place_id=%s error=%s",
                place_id, exc,
            )

    # =========================================================
    # IMAGE HANDLING
    # =========================================================

    def _handle_images(
        self,
        *,
        db: Session,
        place: Place,
        result: MasterDataResult,
    ) -> None:

        place_id = result.place_id

        if result.images_before == 0:
            # No images at all — run image ingestion
            self._run_image_ingestion(db=db, place=place, result=result)

        elif self._images_weak(db, place_id):
            # Images exist but are weak — try enrichment
            logger.info(
                "master_data_orchestrator.images_weak place_id=%s count=%s",
                place_id,
                result.images_before,
            )
            self._run_image_enrichment(db=db, place=place, result=result)

        else:
            result.image_action = "skipped"

        # Always run bridge for any item images from menu extraction
        self._run_item_image_bridge(db=db, place_id=place_id, result=result)

    def _images_weak(self, db: Session, place_id: str) -> bool:
        """Returns True if place has fewer than threshold strong images."""
        count = (
            db.query(func.count(PlaceImage.id))
            .filter(
                PlaceImage.place_id == place_id,
                PlaceImage.quality_score >= IMAGE_QUALITY_STRONG,
            )
            .scalar()
            or 0
        )
        return count < IMAGES_WEAK_THRESHOLD

    def _run_image_ingestion(
        self,
        *,
        db: Session,
        place: Place,
        result: MasterDataResult,
    ) -> None:
        """Full image ingestion via ImageIngestService (Phase 3 pipeline)."""
        try:
            from app.services.images.image_ingest_service import ImageIngestService

            service = ImageIngestService()
            images = service.ingest_place_images(db=db, place=place, force_refresh=False)

            result.image_action = "ingested"

            logger.info(
                "master_data_orchestrator.images_ingested place_id=%s count=%s",
                result.place_id,
                len(images),
            )

        except Exception as exc:
            result.image_action = "failed"
            result.errors.append(f"image_ingestion: {exc}")
            logger.exception(
                "master_data_orchestrator.image_ingestion_failed place_id=%s error=%s",
                result.place_id,
                exc,
            )

    def _run_image_enrichment(
        self,
        *,
        db: Session,
        place: Place,
        result: MasterDataResult,
    ) -> None:
        """Re-run image ingestion with force_refresh to pick up new images."""
        try:
            from app.services.images.image_ingest_service import ImageIngestService

            service = ImageIngestService()
            images = service.ingest_place_images(db=db, place=place, force_refresh=True)

            result.image_action = "enriched"

            logger.info(
                "master_data_orchestrator.images_enriched place_id=%s count=%s",
                result.place_id,
                len(images),
            )

        except Exception as exc:
            result.image_action = "failed"
            result.errors.append(f"image_enrichment: {exc}")
            logger.exception(
                "master_data_orchestrator.image_enrichment_failed place_id=%s error=%s",
                result.place_id,
                exc,
            )

    def _run_item_image_bridge(
        self,
        *,
        db: Session,
        place_id: str,
        result: MasterDataResult,
    ) -> None:
        """Run Phase 3 bridge for any item-level images from menu extraction."""
        try:
            # Collect image_url values from recently-written menu items
            rows = (
                db.query(MenuItem.image)
                .filter(
                    MenuItem.place_id == place_id,
                    MenuItem.image.isnot(None),
                    MenuItem.is_active.is_(True),
                )
                .all()
            )

            image_urls = [r[0] for r in rows if r[0]]

            if not image_urls:
                return

            bridge_result = self._image_bridge.ingest(
                db=db,
                place_id=place_id,
                image_urls=image_urls,
                source="menu_item_image",
            )

            result.item_images_bridged = bridge_result.get("inserted", 0)

            logger.info(
                "master_data_orchestrator.item_images_bridged place_id=%s %s",
                place_id,
                bridge_result,
            )

        except Exception as exc:
            result.errors.append(f"item_image_bridge: {exc}")
            logger.exception(
                "master_data_orchestrator.item_image_bridge_failed place_id=%s error=%s",
                place_id,
                exc,
            )

    # =========================================================
    # HELPERS
    # =========================================================

    def _count_menu_items(self, db: Session, place_id: str) -> int:
        return (
            db.query(func.count(MenuItem.id))
            .filter(
                MenuItem.place_id == place_id,
                MenuItem.is_active.is_(True),
            )
            .scalar()
            or 0
        )

    def _count_images(self, db: Session, place_id: str) -> int:
        return (
            db.query(func.count(PlaceImage.id))
            .filter(PlaceImage.place_id == place_id)
            .scalar()
            or 0
        )
