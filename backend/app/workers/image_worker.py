from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import exists, func, not_, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage, VISIBILITY_HIDDEN
from app.services.images.image_ingest_service import ImageIngestService
from app.services.images.place_image_invariant_service import PlaceImageInvariantService
from app.services.images.stale_image_refresher import StaleImageRefresher
from app.services.cache.cache_helpers import invalidate_place, invalidate_all_image_caches


logger = logging.getLogger(__name__)

UTC = timezone.utc

DEFAULT_BATCH_SIZE = 50
MAX_BATCH_SIZE = 200

MIN_IMAGE_COUNT = 3
STALE_IMAGE_DAYS = 30
MAX_FETCH_ATTEMPTS = 3


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ImageWorker:
    """
    Production image ingestion worker.

    Responsibilities
    ----------------
    - select places that need image ingestion
    - backfill places with no images
    - refresh places with too few images
    - refresh places with missing primary image
    - refresh stale image galleries
    - support forced refresh and targeted place ids
    - isolate failures per place
    - keep processing deterministic and bounded
    """

    def __init__(
        self,
        *,
        ingest_service: Optional[ImageIngestService] = None,
        invariant_service: Optional[PlaceImageInvariantService] = None,
        stale_refresher: Optional[StaleImageRefresher] = None,
    ) -> None:
        self.ingest_service = ingest_service or ImageIngestService()
        self.invariant_service = invariant_service or PlaceImageInvariantService()
        self.stale_refresher = stale_refresher or StaleImageRefresher()

    # ---------------------------------------------------------
    # Worker entrypoint
    # ---------------------------------------------------------

    def run(
        self,
        *,
        db: Session,
        limit: int = DEFAULT_BATCH_SIZE,
        force_refresh: bool = False,
        place_ids: Optional[List[str]] = None,
    ) -> Dict[str, int]:

        limit = self._normalize_limit(limit)

        places, stale_refresh_ids = self._select_places(
            db=db,
            limit=limit,
            force_refresh=force_refresh,
            place_ids=place_ids,
        )

        if not places:

            logger.info(
                "image_worker_no_places force_refresh=%s limit=%s",
                force_refresh,
                limit,
            )

            return {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "images_written": 0,
            }

        logger.info(
            "image_worker_start places=%s force_refresh=%s limit=%s",
            len(places),
            force_refresh,
            limit,
        )

        processed = 0
        succeeded = 0
        failed = 0
        images_written = 0

        for place in places:

            processed += 1

            place_id = getattr(place, "id", None)
            attempt_failed = False
            is_stale_refresh = place_id in stale_refresh_ids

            try:

                if is_stale_refresh:
                    # Deliberately NOT ingest_service.ingest_place_images —
                    # see StaleImageRefresher's own docstring for why
                    # running the normal gallery-rebuild pipeline here
                    # would accumulate a fresh, never-pruned set of gallery
                    # rows for this place every ~30 days instead of just
                    # replacing the one image that's actually stale.
                    ok = self.stale_refresher.refresh_primary(db=db, place=place)
                    written_count = 1 if ok else 0
                    attempt_failed = not ok
                else:
                    images = self.ingest_service.ingest_place_images(
                        db=db,
                        place=place,
                        force_refresh=force_refresh,
                    )
                    written_count = len(images)

                    # Count as a failed attempt if no images were returned
                    if not images:
                        attempt_failed = True

                succeeded += 1
                images_written += written_count

                logger.debug(
                    "image_worker_place_complete place_id=%s images=%s",
                    place_id,
                    written_count,
                )

            except Exception as exc:

                db.rollback()

                attempt_failed = True
                failed += 1

                logger.exception(
                    "image_worker_place_failed place_id=%s error=%s",
                    place_id,
                    exc,
                )

            # Track fetch attempts and block after MAX_FETCH_ATTEMPTS failures
            if attempt_failed and not force_refresh and place_id:
                try:
                    new_attempts = getattr(place, "image_fetch_attempts", 0) + 1
                    should_block = new_attempts >= MAX_FETCH_ATTEMPTS
                    db.execute(
                        update(Place)
                        .where(Place.id == place_id)
                        .values(
                            image_fetch_attempts=new_attempts,
                            image_blocked=should_block,
                        )
                    )
                    db.commit()
                    if should_block:
                        logger.warning(
                            "image_worker_place_blocked place_id=%s attempts=%s",
                            place_id,
                            new_attempts,
                        )
                except Exception:
                    db.rollback()
                    logger.exception(
                        "image_worker_attempt_update_failed place_id=%s",
                        place_id,
                    )
            elif not attempt_failed:
                # Commit succeeded path (images returned)
                # Run invariant repair before commit to keep DB consistent
                if place_id:
                    try:
                        self.invariant_service.repair(db=db, place_id=place_id)
                    except Exception:
                        logger.debug(
                            "image_worker_invariant_repair_failed place_id=%s",
                            place_id,
                        )
                db.commit()
                if place_id:
                    try:
                        invalidate_place(place_id)
                        invalidate_all_image_caches()
                    except Exception:
                        logger.debug(
                            "image_worker_cache_invalidate_failed place_id=%s",
                            place_id,
                        )

        result = {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "images_written": images_written,
        }

        logger.info(
            "image_worker_complete processed=%s succeeded=%s failed=%s images_written=%s",
            processed,
            succeeded,
            failed,
            images_written,
        )

        return result

    # ---------------------------------------------------------
    # Place selection logic
    # ---------------------------------------------------------

    def _select_places(
        self,
        *,
        db: Session,
        limit: int,
        force_refresh: bool,
        place_ids: Optional[List[str]],
    ) -> Tuple[List[Place], Set[str]]:

        # ImageIngestService (._has_existing_images) reads place.images, and
        # ProviderImageExtractor (reached via ImageReader further down this
        # same pipeline) reads place.claims -- both default to lazy loading
        # now (see category.py's comment for why), so this batch fetch needs
        # its own explicit eager-load options to avoid a per-place query for
        # each in the loop below. Same pattern recompute_scores.py already
        # uses for Place.categories.
        base_stmt = select(Place).options(
            selectinload(Place.images), selectinload(Place.claims),
        ).where(
            Place.is_active.is_(True),
        )

        if place_ids:
            base_stmt = base_stmt.where(Place.id.in_(place_ids))

        if not force_refresh:
            base_stmt = base_stmt.where(self._needs_image_work_clause())
            base_stmt = base_stmt.where(Place.image_blocked.is_not(True))

        priority_stmt = base_stmt.order_by(
            Place.rank_score.desc(),
            Place.confidence_score.desc(),
            Place.created_at.asc(),
        )

        # An explicit place list or a forced refresh means the caller wants
        # exactly those places, in priority order — no fairness split.
        if place_ids or force_refresh or limit < 2:
            return list(db.execute(priority_stmt.limit(limit)).scalars().all()), set()

        # Reserve a slice of the batch for the oldest places that still need
        # work, regardless of rank_score. Without this, a place with a
        # naturally low rank_score (e.g. a small town with few signals) can
        # be permanently outranked by every other place still needing image
        # work — discovery keeps adding new, higher-signal candidates that
        # refill the top of the rank_score-ordered queue, so a straight
        # ORDER BY rank_score DESC LIMIT never reaches it. Confirmed in
        # production: Lodi's 48 places sat at zero images across 622
        # consecutive successful worker runs because none of them ever
        # cracked the top `limit` by rank_score. Same starvation shape
        # menu_worker.py's own comments warn about for its batch query.
        #
        # A second, separate reserve handles a different failure mode:
        # Google's Places API (New) photo resource names are not permanent
        # — confirmed live in production, a currently-listed, currently-
        # active place's stored primary_image_url 404'd from Google's own
        # media endpoint. _needs_image_work_clause() only selects places
        # with too few images or no primary at all, so once a place clears
        # that bar even once, it is NEVER revisited by a normal run again —
        # there is no automatic path that ever notices an existing photo
        # reference has gone stale. STALE_IMAGE_DAYS existed as a constant
        # for this but was never wired to anything; this reserve is what
        # actually uses it. Bounded (like the starvation reserve above) so
        # a 29k+-place catalog doesn't spend the whole batch re-verifying
        # old-but-still-valid photos instead of backfilling places with
        # none at all.
        starvation_reserve = max(1, limit // 5)
        stale_reserve = max(1, limit // 10)
        priority_limit = max(1, limit - starvation_reserve - stale_reserve)

        priority_places = list(
            db.execute(priority_stmt.limit(priority_limit)).scalars().all()
        )
        picked_ids = {p.id for p in priority_places}

        fairness_stmt = base_stmt.order_by(
            Place.created_at.asc(), Place.id.asc()
        ).limit(starvation_reserve + len(picked_ids))
        fairness_places = [
            p for p in db.execute(fairness_stmt).scalars().all()
            if p.id not in picked_ids
        ][:starvation_reserve]
        picked_ids.update(p.id for p in fairness_places)

        # Base filters only (is_active, place_ids, image_blocked) — NOT
        # _needs_image_work_clause, since a stale-but-present primary image
        # deliberately doesn't match that clause at all.
        stale_base_stmt = select(Place).options(
            selectinload(Place.images), selectinload(Place.claims),
        ).where(Place.is_active.is_(True))
        if place_ids:
            stale_base_stmt = stale_base_stmt.where(Place.id.in_(place_ids))
        stale_base_stmt = stale_base_stmt.where(Place.image_blocked.is_not(True))

        stale_cutoff = _utcnow() - timedelta(days=STALE_IMAGE_DAYS)
        # A scalar subquery (not a join) specifically so DISTINCT/ORDER BY
        # never has to reconcile a joined column against a query that only
        # selects Place — Postgres rejects ORDER BY on a column outside the
        # SELECT list under SELECT DISTINCT, which a join here would risk.
        primary_created_at_subquery = (
            select(PlaceImage.created_at)
            .where(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
            )
            .order_by(PlaceImage.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        stale_stmt = (
            stale_base_stmt.where(self._stale_primary_clause(stale_cutoff))
            .order_by(primary_created_at_subquery.asc())
            .limit(stale_reserve + len(picked_ids))
        )
        stale_places = [
            p for p in db.execute(stale_stmt).scalars().all()
            if p.id not in picked_ids
        ][:stale_reserve]
        picked_ids.update(p.id for p in stale_places)

        # The stale-refresh reserve above legitimately returns fewer than
        # stale_reserve whenever there simply aren't that many old-enough
        # primary images yet (the common case for a catalog still mostly
        # backfilling from scratch) — that reserved capacity would
        # otherwise just go unused and silently shrink the batch below
        # `limit`. Backfill with the next-best priority-ordered places
        # instead, using the same over-fetch-then-filter pattern as the
        # fairness reserve above (limit by shortfall + len(picked_ids) to
        # guarantee enough surplus after excluding everything already
        # picked, rather than risk the backfill query's own limit landing
        # entirely inside already-picked rows).
        already_selected = len(priority_places) + len(fairness_places) + len(stale_places)
        shortfall = limit - already_selected
        if shortfall > 0:
            backfill_stmt = priority_stmt.limit(shortfall + len(picked_ids))
            backfill_places = [
                p for p in db.execute(backfill_stmt).scalars().all()
                if p.id not in picked_ids
            ][:shortfall]
        else:
            backfill_places = []

        stale_refresh_ids = {p.id for p in stale_places}

        return (
            priority_places + fairness_places + stale_places + backfill_places,
            stale_refresh_ids,
        )

    def _stale_primary_clause(self, stale_cutoff: datetime):
        """
        True when a place's current primary image was set before
        stale_cutoff — i.e. it's old enough that its Google photo reference
        (if that's the source) may no longer resolve. See _select_places'
        stale-refresh reserve for why this needs its own periodic,
        automatic path instead of only firing on explicit force_refresh.
        """
        return exists(
            select(PlaceImage.id).where(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
                PlaceImage.created_at < stale_cutoff,
            )
        )

    def _needs_image_work_clause(self):
        """
        Select places that need image work:
        - no images at all, OR
        - fewer than MIN_IMAGE_COUNT images, OR
        - no primary image set

        Stale refresh (images older than STALE_IMAGE_DAYS) is handled by a
        separate, bounded reserve in _select_places instead — see there for
        why it can't just be added to this clause outright.
        """
        total_images_subquery = (
            select(func.count(PlaceImage.id))
            .where(PlaceImage.place_id == Place.id)
            .scalar_subquery()
        )

        primary_exists_clause = exists(
            select(PlaceImage.id).where(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
            )
        )

        any_images_clause = exists(
            select(PlaceImage.id).where(
                PlaceImage.place_id == Place.id,
            )
        )

        # Re-process places whose current primary is hidden (invariant violation)
        hidden_primary_clause = exists(
            select(PlaceImage.id).where(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
                PlaceImage.visibility_status == VISIBILITY_HIDDEN,
            )
        )

        return or_(
            not_(any_images_clause),
            total_images_subquery < MIN_IMAGE_COUNT,
            not_(primary_exists_clause),
            hidden_primary_clause,
        )

    # ---------------------------------------------------------
    # Limit guard
    # ---------------------------------------------------------

    def _normalize_limit(
        self,
        limit: int,
    ) -> int:

        try:
            limit = int(limit)
        except Exception:
            return DEFAULT_BATCH_SIZE

        if limit <= 0:
            return DEFAULT_BATCH_SIZE

        if limit > MAX_BATCH_SIZE:
            return MAX_BATCH_SIZE

        return limit