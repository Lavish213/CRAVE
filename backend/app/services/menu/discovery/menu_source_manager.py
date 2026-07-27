"""
MenuSourceManager — durable source lineage for menu extraction.

Rules enforced:
- Multiple candidates per place allowed; highest-confidence active source wins.
- Lower-confidence providers CANNOT overwrite higher-confidence active sources.
- Failed providers track degradation via failure_count.
- Providers with failure_count >= FAILURE_THRESHOLD are auto-demoted (is_active=False).
- places.menu_source_url is a denormalized pointer — only updated when active source changes.

Provider precedence (higher = more trusted):
    toast=10, popmenu=9, square=8, chownow=8, clover=7, olo=6,
    direct_html=3, grubhub=2, aggregator=1
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.menu_source import MenuSource
from app.db.models.place import Place


logger = logging.getLogger(__name__)

# How many consecutive failures before a source is auto-demoted
FAILURE_THRESHOLD = 5

# Provider name → trust rank (higher = more trusted)
PROVIDER_PRECEDENCE: dict[str, int] = {
    "toast":       10,
    "popmenu":     9,
    "square":      8,
    "chownow":     8,
    "clover":      7,
    "olo":         6,
    "direct_html": 3,
    "grubhub":     2,
    "aggregator":  1,
    "html":        1,
    "unknown":     0,
}


def _source_hash(url: str) -> str:
    """Stable identity for a source URL."""
    return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MenuSourceManager:
    """
    Manages the menu_sources table: discovery, promotion, demotion, failure tracking.
    All methods take an open Session; callers are responsible for commit.
    """

    def record_discovery(
        self,
        *,
        db: Session,
        place_id: str,
        source_url: str,
        provider: Optional[str],
        source_type: str,
        confidence: float,
    ) -> MenuSource:
        """
        Record a newly discovered menu source candidate.
        Creates or updates the MenuSource row.
        Does NOT overwrite a higher-confidence active source with a lower-confidence one.

        Returns the MenuSource row (new or existing).
        """
        url = source_url.strip()
        sh = _source_hash(url)

        existing = (
            db.query(MenuSource)
            .filter(
                MenuSource.place_id == place_id,
                MenuSource.source_hash == sh,
            )
            .one_or_none()
        )

        now = _now()

        if existing:
            # Update last_seen and confidence if this probe is fresher/more confident
            existing.last_seen_at = now
            existing.last_verified_at = now
            if confidence > existing.confidence:
                existing.confidence = confidence
            if provider and not existing.provider:
                existing.provider = provider
            return existing

        # New source — check if it would overwrite a better active source
        best_active = self._get_best_active_source(db, place_id)
        if best_active and best_active.confidence >= confidence:
            new_rank = PROVIDER_PRECEDENCE.get((provider or "").lower(), 0)
            best_rank = PROVIDER_PRECEDENCE.get((best_active.provider or "").lower(), 0)
            if new_rank < best_rank:
                logger.debug(
                    "menu_source_discovery_suppressed place_id=%s "
                    "new_provider=%s new_confidence=%.2f "
                    "best_provider=%s best_confidence=%.2f",
                    place_id, provider, confidence,
                    best_active.provider, best_active.confidence,
                )
                # Still record it as inactive candidate — useful for auditing
                source = MenuSource(
                    place_id=place_id,
                    source_url=url,
                    source_hash=sh,
                    provider=provider,
                    source_type=source_type,
                    confidence=confidence,
                    is_active=False,  # suppressed — lower precedence
                    discovered_at=now,
                    last_seen_at=now,
                    last_verified_at=now,
                    failure_count=0,
                )
                db.add(source)
                return source

        source = MenuSource(
            place_id=place_id,
            source_url=url,
            source_hash=sh,
            provider=provider,
            source_type=source_type,
            confidence=confidence,
            is_active=True,
            discovered_at=now,
            last_seen_at=now,
            last_verified_at=now,
            failure_count=0,
        )
        db.add(source)
        logger.info(
            "menu_source_discovered place_id=%s provider=%s confidence=%.2f url=%s",
            place_id, provider, confidence, url,
        )
        return source

    def record_success(
        self,
        *,
        db: Session,
        place_id: str,
        source_url: str,
    ) -> None:
        """Mark a source as successfully extracted. Reset failure count."""
        sh = _source_hash(source_url)
        source = (
            db.query(MenuSource)
            .filter(MenuSource.place_id == place_id, MenuSource.source_hash == sh)
            .one_or_none()
        )
        if source:
            now = _now()
            source.last_success_at = now
            source.last_verified_at = now
            source.failure_count = 0
            source.is_active = True
            source.invalidated_at = None
            source.invalidation_reason = None

    def record_failure(
        self,
        *,
        db: Session,
        place_id: str,
        source_url: str,
        reason: Optional[str] = None,
    ) -> None:
        """Increment failure count. Auto-demote source after FAILURE_THRESHOLD."""
        sh = _source_hash(source_url)
        source = (
            db.query(MenuSource)
            .filter(MenuSource.place_id == place_id, MenuSource.source_hash == sh)
            .one_or_none()
        )
        if not source:
            return

        source.failure_count += 1
        source.last_verified_at = _now()

        if source.failure_count >= FAILURE_THRESHOLD:
            source.is_active = False
            source.invalidated_at = _now()
            source.invalidation_reason = reason or f"failure_count>={FAILURE_THRESHOLD}"
            logger.warning(
                "menu_source_demoted place_id=%s provider=%s url=%s reason=%s",
                place_id, source.provider, source_url,
                source.invalidation_reason,
            )
            # Sync places.menu_source_url to next best active source
            self._sync_place_menu_source_url(db, place_id)

    def get_best_source_url(self, *, db: Session, place_id: str) -> Optional[str]:
        """Return the URL of the highest-confidence active source."""
        best = self._get_best_active_source(db, place_id)
        return best.source_url if best else None

    def _get_best_active_source(
        self, db: Session, place_id: str
    ) -> Optional[MenuSource]:
        from sqlalchemy import case
        # Build a CASE expression mapping provider → precedence rank (SA 2.0 syntax).
        # Ties in confidence broken by provider precedence then by freshness.
        precedence_case = case(
            *[
                (MenuSource.provider == provider, rank)
                for provider, rank in PROVIDER_PRECEDENCE.items()
            ],
            else_=0,
        )
        return (
            db.query(MenuSource)
            .filter(
                MenuSource.place_id == place_id,
                MenuSource.is_active.is_(True),
            )
            .order_by(
                MenuSource.confidence.desc(),
                precedence_case.desc(),
                MenuSource.last_verified_at.desc(),
            )
            .first()
        )

    def _sync_place_menu_source_url(self, db: Session, place_id: str) -> None:
        """
        Keep places.menu_source_url in sync with the best active MenuSource.
        This is a denormalized cache field — always derived from menu_sources.
        """
        place = (
            db.query(Place)
            .filter(Place.id == place_id)
            .one_or_none()
        )
        if not place:
            return

        best = self._get_best_active_source(db, place_id)
        new_url = best.source_url if best else None

        if place.menu_source_url != new_url:
            place.menu_source_url = new_url
            logger.info(
                "place_menu_source_url_synced place_id=%s url=%s",
                place_id, new_url,
            )


# Module-level singleton — stateless service
menu_source_manager = MenuSourceManager()
