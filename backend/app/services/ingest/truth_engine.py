from __future__ import annotations

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place import Place


logger = logging.getLogger(__name__)


MIN_CONFIDENCE = 0.8
DEFAULT_LIMIT = 500


def promote_candidates_to_places(limit: int = DEFAULT_LIMIT) -> int:

    db: Session = SessionLocal()

    created = 0
    skipped = 0
    failed = 0

    try:

        candidates = _fetch_candidates(db, limit)

        if not candidates:
            logger.info("truth_engine_no_candidates")
            return 0

        logger.info(
            "truth_engine_start total_candidates=%s",
            len(candidates),
        )

        for c in candidates:

            try:

                # -------------------------------------------------
                # VALIDATION
                # -------------------------------------------------

                if not c.name or not c.city_id:
                    skipped += 1
                    _mark_processed(c)
                    continue

                # -------------------------------------------------
                # DUPLICATE CHECK (STRONGER)
                # -------------------------------------------------

                if _place_exists(db, c):
                    skipped += 1
                    _mark_processed(c)
                    continue

                # -------------------------------------------------
                # BUILD
                # -------------------------------------------------

                place = _build_place(c)

                if not place:
                    failed += 1
                    _mark_processed(c)
                    continue

                db.add(place)
                db.flush()

                created += 1

                _mark_processed(c)

            except Exception as row_error:
                failed += 1

                logger.exception(
                    "truth_engine_row_failed candidate_id=%s error=%s",
                    getattr(c, "id", None),
                    row_error,
                )

        db.commit()

        logger.info(
            "truth_engine_complete created=%s skipped=%s failed=%s",
            created,
            skipped,
            failed,
        )

        return created

    except SQLAlchemyError as db_error:
        db.rollback()
        logger.exception("truth_engine_db_failed error=%s", db_error)
        return 0

    except Exception as exc:
        db.rollback()
        logger.exception("truth_engine_failed error=%s", exc)
        return 0

    finally:
        db.close()


# =========================================================
# FETCH
# =========================================================

def _fetch_candidates(db: Session, limit: int) -> List[DiscoveryCandidate]:

    stmt = (
        select(DiscoveryCandidate)
        .where(
            DiscoveryCandidate.confidence_score >= MIN_CONFIDENCE,
            DiscoveryCandidate.is_promoted.is_(False),  # 🔥 prevents reprocessing
        )
        .order_by(DiscoveryCandidate.confidence_score.desc())
        .limit(limit)
    )

    results = db.execute(stmt).scalars().all()

    logger.info(
        "truth_engine_candidates_loaded count=%s",
        len(results),
    )

    return results


# =========================================================
# EXISTENCE CHECK (IMPROVED)
# =========================================================

def _place_exists(db: Session, candidate: DiscoveryCandidate) -> bool:

    stmt = select(Place.id).where(
        Place.name == candidate.name,
        Place.city_id == candidate.city_id,
    )

    existing = db.execute(stmt).first()

    if existing:
        return True

    # 🔥 SECONDARY CHECK (geo proximity)
    if candidate.lat is not None and candidate.lng is not None:

        stmt = select(Place.id).where(
            Place.city_id == candidate.city_id,
            Place.lat.isnot(None),
            Place.lng.isnot(None),
        )

        for (pid,) in db.execute(stmt):
            # simple proximity check
            if abs(candidate.lat - (pid or 0)) < 0.0005:
                return True

    return False


# =========================================================
# BUILD PLACE
# =========================================================

def _build_place(candidate: DiscoveryCandidate) -> Place | None:

    try:

        name = candidate.name.strip() if candidate.name else None
        city_id = candidate.city_id

        lat = candidate.lat
        lng = candidate.lng

        if not name or not city_id:
            return None

        if lat is not None and not (-90 <= lat <= 90):
            lat = None

        if lng is not None and not (-180 <= lng <= 180):
            lng = None

        return Place(
            name=name,
            city_id=city_id,
            lat=lat,
            lng=lng,
        )

    except Exception:
        logger.exception(
            "truth_engine_build_failed candidate_id=%s",
            getattr(candidate, "id", None),
        )
        return None


# =========================================================
# MARK PROCESSED (CRITICAL)
# =========================================================

def _mark_processed(candidate: DiscoveryCandidate) -> None:
    try:
        candidate.is_promoted = True
    except Exception:
        pass