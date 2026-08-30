from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_truth import PlaceTruth

from app.services.menu.processing.menu_orchestrator import MenuOrchestrator
from app.workers.recompute_scores_worker import recompute_places_v4


logger = logging.getLogger(__name__)


# Bumped from 25/200 — with the discovery pipeline now finding real
# places (OSM confidence fix + Overture Maps), the sourced-but-unchecked
# backlog (12,123 places with a website/Grubhub/menu URL, only 761 with an
# extracted menu as of the live check that prompted this) is growing
# faster than extraction can work through it at the old rate. Kept
# moderate rather than maxed out: the scheduler runs embedded in the same
# single process serving web requests (no separate worker service is
# actually deployed), so this isn't free — a much larger jump risks
# competing with real traffic instead of just catching up on backlog.
BATCH_SIZE = 40
MAX_PLACES_PER_RUN = 300
SLEEP_BETWEEN_BATCHES = 1.0

MENU_TRUTH_TYPE = "menu"

# Place.menu_extraction_failure_count / menu_extraction_attempted_at have
# existed since the truth-stabilization migration with this exact schedule
# in their column comments ("Progressive backoff: 1=1h, 2=4h, 3=24h,
# 4+=72h") — but nothing ever wrote to them. _load_places_requiring_menu
# only ever excluded places that already have a menu PlaceTruth row, and
# materialize_menu_truth only ever writes one on SUCCESS (0 items or too
# few items both return early with no row written at all). So a place
# that structurally can't yield a menu — a JS-walled site, a PDF the
# extractor can't parse, a domain that's down — was retried on every
# single 10-minute run, forever, with zero backoff.
#
# That's not just wasted work: since the query orders by rank_score DESC
# and LIMIT's to BATCH_SIZE with no offset, a handful of high-ranked,
# permanently-failing places could occupy the entire batch window on
# every run and starve the rest of the catalog from ever being attempted
# — the single biggest lever on menu coverage, worse than any extractor
# quality issue, because it means most of the catalog was never even
# tried.
_BACKOFF_HOURS = {1: 1, 2: 4, 3: 24}
_BACKOFF_HOURS_MAX = 72  # failure_count >= 4

# How long a successfully-extracted menu is trusted before it's eligible to
# be re-checked (menus go stale — price changes, a redesign that breaks the
# extractor, a place that closed). See _load_places_requiring_menu's
# docstring for the full reasoning.
MENU_STALENESS_DAYS = 60


def _valid_http_source(column):
    # Require a dotted host, not merely a scheme. Production contained both
    # a bare label (``SpritzersCafe``) and ``https://+15106716333``; neither is
    # a fetchable web source even though the latter begins with https://.
    return or_(column.ilike("http://%.%"), column.ilike("https://%.%"))


def _source_quality_clause():
    """Prefer sources most likely to contain extractable menu truth.

    Direct discovered menu sources and provider URLs outrank generic websites;
    chain locator/store pages are deliberately demoted. This is queue ordering,
    not acceptance: every extracted result still passes the normal plausibility
    and materialization gates.
    """
    direct = func.lower(func.coalesce(Place.menu_source_url, ""))
    grubhub = func.lower(func.coalesce(Place.grubhub_url, ""))
    website = func.lower(func.coalesce(Place.website, ""))
    best = case(
        (_valid_http_source(Place.menu_source_url), direct),
        (_valid_http_source(Place.grubhub_url), grubhub),
        else_=website,
    )
    has_menu_signal = or_(
        best.like("%/menu%"),
        best.like("%menu.%"),
        best.like("%.pdf%"),
        best.like("%order%"),
        best.like("%toasttab%"),
        best.like("%chownow%"),
        best.like("%clover%"),
        best.like("%popmenu%"),
        best.like("%square%"),
        best.like("%menufy%"),
        best.like("%grubhub%"),
    )
    is_locator = or_(
        best.like("%://locations.%"),
        best.like("%://restaurants.%"),
        best.like("%/locations/%"),
        best.like("%/location/%"),
        best.like("%store-locator%"),
    )
    return case(
        (_valid_http_source(Place.menu_source_url), 100),
        (_valid_http_source(Place.grubhub_url), 90),
        (has_menu_signal, 80),
        (is_locator, 10),
        else_=40,
    )


def _not_in_backoff_clause(now: datetime):
    return or_(
        Place.menu_extraction_attempted_at.is_(None),
        # 0 (or never-set) failures is never "in backoff" — backoff only
        # means something once there's been an actual failure. Without this
        # branch, a healthy place whose menu_extraction_failure_count was
        # reset to 0 on success (see run()'s materialized branch) would be
        # wrongly excluded here forever once MENU_STALENESS_DAYS made it
        # eligible again — none of the count==1/2/3/4+ branches below ever
        # match count 0, so it would look "in backoff" despite never having
        # failed at all.
        Place.menu_extraction_failure_count.is_(None),
        Place.menu_extraction_failure_count == 0,
        *[
            and_(
                Place.menu_extraction_failure_count == count,
                Place.menu_extraction_attempted_at <= now - timedelta(hours=hours),
            )
            for count, hours in _BACKOFF_HOURS.items()
        ],
        and_(
            Place.menu_extraction_failure_count >= 4,
            Place.menu_extraction_attempted_at <= now - timedelta(hours=_BACKOFF_HOURS_MAX),
        ),
    )


class MenuWorker:

    def __init__(self):
        self.orchestrator = MenuOrchestrator()

    def run(
        self,
        *,
        max_places: int | None = None,
        city_id: str | None = None,
    ) -> dict[str, int]:

        if max_places is None:
            max_places = MAX_PLACES_PER_RUN
        max_places = max(1, min(MAX_PLACES_PER_RUN, int(max_places)))

        total_processed = 0
        error_count = 0
        materialized_count = 0
        no_menu_count = 0

        while total_processed < max_places:

            db: Session = SessionLocal()

            try:

                places = self._load_places_requiring_menu(
                    db,
                    city_id=city_id,
                    limit=min(BATCH_SIZE, max_places - total_processed),
                )

                if not places:
                    logger.info("menu_worker_no_more_places")
                    break

                logger.info(
                    "menu_worker_batch_start batch_size=%s processed=%s",
                    len(places),
                    total_processed,
                )

                for place in places:

                    try:

                        result = self.orchestrator.run_for_place(
                            db=db,
                            place=place,
                        )

                        total_processed += 1
                        materialized = getattr(result, "materialized", False)

                        if materialized:
                            materialized_count += 1
                            # Set has_menu flag and recompute score after successful materialization
                            place.has_menu = True
                            place.menu_extraction_failure_count = 0
                            # Also stamped on success (not just failure) —
                            # this is the staleness clock _load_places_
                            # requiring_menu uses to eventually re-check an
                            # already-menu'd place. materialize_menu_truth
                            # skips writing PlaceTruth.updated_at when a
                            # re-extraction hashes identical to what's
                            # already there (see its own dedup check), so
                            # that column alone can't be used for this —
                            # a place whose menu never changes would get
                            # re-attempted every single cycle forever.
                            place.menu_extraction_attempted_at = datetime.now(timezone.utc)
                            recompute_places_v4(db, places=[place])
                        else:
                            no_menu_count += 1
                            # No PlaceTruth was written (see module docstring) —
                            # record the attempt so this place backs off instead
                            # of occupying every future batch.
                            place.menu_extraction_attempted_at = datetime.now(timezone.utc)
                            place.menu_extraction_failure_count = (
                                place.menu_extraction_failure_count or 0
                            ) + 1

                        logger.info(
                            "menu_worker_place_complete place_id=%s sources=%s extracted=%s claims=%s materialized=%s",
                            place.id,
                            getattr(result, "source_count", 0),
                            getattr(result, "extracted_item_count", 0),
                            getattr(result, "emitted_claim_count", 0),
                            materialized,
                        )

                        db.commit()

                    except Exception as exc:

                        db.rollback()
                        error_count += 1

                        logger.exception(
                            "menu_worker_place_failed place_id=%s error=%s",
                            place.id,
                            exc,
                        )

                        # Same backoff bookkeeping as the "ran but came up
                        # empty" branch above — an exception here (fetch
                        # timeout, parser crash, whatever) is just as much a
                        # reason to back off this place as an empty result,
                        # and it must land in its own transaction since the
                        # main one was just rolled back.
                        try:
                            retry_place = (
                                db.query(Place).filter(Place.id == place.id).one_or_none()
                            )
                            if retry_place is not None:
                                retry_place.menu_extraction_attempted_at = datetime.now(timezone.utc)
                                retry_place.menu_extraction_failure_count = (
                                    retry_place.menu_extraction_failure_count or 0
                                ) + 1
                                db.commit()
                        except Exception:
                            db.rollback()
                            logger.exception(
                                "menu_worker_failure_bookkeeping_failed place_id=%s",
                                place.id,
                            )

                    if total_processed >= max_places:
                        break

                logger.info(
                    "menu_worker_batch_complete processed=%s errors=%s",
                    total_processed,
                    error_count,
                )

            finally:
                db.close()

            time.sleep(SLEEP_BETWEEN_BATCHES)

        logger.info(
            "menu_worker_run_complete total_processed=%s errors=%s materialized=%s no_menu=%s",
            total_processed,
            error_count,
            materialized_count,
            no_menu_count,
        )

        return {
            "attempted": total_processed,
            "errors": error_count,
            "materialized": materialized_count,
            "no_menu": no_menu_count,
        }

    def _load_places_requiring_menu(
        self,
        db: Session,
        *,
        city_id: str | None = None,
        limit: int = BATCH_SIZE,
    ) -> List[Place]:

        limit = max(1, min(MAX_PLACES_PER_RUN, int(limit)))

        # Was: only Place.website IS NOT NULL. That silently skipped every
        # place whose only menu source is a delivery-platform URL (Grubhub)
        # or a directly-discovered menu_source_url without a general website
        # on file — a real and common case, not an edge case.
        #
        # Was also: PlaceTruth.id.is_(None) as the ONLY eligibility gate —
        # meaning a place that ever successfully got a menu was excluded
        # from every future run, forever, with no way to notice a menu
        # going stale (prices change, a restaurant closes, a site
        # redesign breaks the extractor). Now also eligible: an existing
        # menu whose last real check (Place.menu_extraction_attempted_at,
        # stamped on both success and failure — see run()'s materialized
        # branch) is past MENU_STALENESS_DAYS, or was never stamped at all
        # (every place with a menu from before this staleness mechanism
        # existed — treated as eligible for one catch-up check rather than
        # needing a data migration to backfill the column).
        now = datetime.now(timezone.utc)
        staleness_cutoff = now - timedelta(days=MENU_STALENESS_DAYS)

        base_query = (
            db.query(Place)
            .outerjoin(
                PlaceTruth,
                (PlaceTruth.place_id == Place.id)
                & (PlaceTruth.truth_type == MENU_TRUTH_TYPE),
            )
            .filter(
                or_(
                    _valid_http_source(Place.website),
                    _valid_http_source(Place.grubhub_url),
                    _valid_http_source(Place.menu_source_url),
                ),
                or_(
                    PlaceTruth.id.is_(None),
                    Place.menu_extraction_attempted_at.is_(None),
                    Place.menu_extraction_attempted_at <= staleness_cutoff,
                ),
                _not_in_backoff_clause(now),
            )
        )

        if city_id:
            base_query = base_query.filter(Place.city_id == city_id)

        # Reserve a slice of the batch for the oldest eligible places
        # regardless of rank_score. Without this, a straight
        # `rank_score DESC LIMIT BATCH_SIZE` never-attempted place with a
        # low rank_score can be permanently outranked by newer, higher-signal
        # places — discovery keeps refilling the top of the queue, so it
        # never cracks the top BATCH_SIZE and is never even tried. Same
        # starvation shape the module docstring above warns about (confirmed
        # in production for the identical pattern in image_worker.py's
        # _select_places, which this mirrors). The backoff clause already
        # applied above prevents a repeat-failing place from hogging every
        # run — this fixes the separate case of a place that's simply
        # never been attempted at all.
        starvation_reserve = 0 if limit == 1 else max(1, limit // 5)
        priority_limit = limit - starvation_reserve

        priority_places = list(
            base_query.order_by(
                func.coalesce(Place.menu_extraction_failure_count, 0).asc(),
                _source_quality_clause().desc(),
                Place.rank_score.desc(),
                Place.id.asc(),
            )
            .limit(priority_limit)
            .all()
        )
        picked_ids = {p.id for p in priority_places}

        fairness_places = [
            p
            for p in base_query.order_by(
                Place.created_at.asc(), Place.id.asc()
            )
            .limit(starvation_reserve + len(picked_ids))
            .all()
            if p.id not in picked_ids
        ][:starvation_reserve]

        places = priority_places + fairness_places

        logger.info(
            "menu_worker_places_loaded count=%s priority=%s fairness=%s",
            len(places),
            len(priority_places),
            len(fairness_places),
        )

        return places


def run_menu_worker():
    worker = MenuWorker()
    worker.run()
