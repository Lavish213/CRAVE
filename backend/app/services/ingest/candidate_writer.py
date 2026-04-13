from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, List

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.db.models.discovery_candidate import DiscoveryCandidate


logger = logging.getLogger(__name__)

UTC = timezone.utc
BATCH_LOOKUP_SIZE = 1000


# -----------------------------------------------------
# HELPERS
# -----------------------------------------------------

def _safe_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _clean_str(value) -> Optional[str]:
    if not value:
        return None
    try:
        v = str(value).strip()
        return v if v else None
    except Exception:
        return None


def _now():
    return datetime.now(UTC)


# -----------------------------------------------------
# WRITER
# -----------------------------------------------------

class CandidateWriter:

    def write(
        self,
        candidates: Iterable[Dict],
    ) -> int:

        db = SessionLocal()

        inserted = 0
        updated = 0
        skipped = 0

        try:

            batch: List[Dict] = []

            for c in candidates:
                if not c:
                    skipped += 1
                    continue

                batch.append(c)

                if len(batch) >= BATCH_LOOKUP_SIZE:
                    i, u, s = self._process_batch(db, batch)
                    inserted += i
                    updated += u
                    skipped += s
                    batch.clear()

            if batch:
                i, u, s = self._process_batch(db, batch)
                inserted += i
                updated += u
                skipped += s

            db.commit()

        except SQLAlchemyError as exc:

            db.rollback()

            logger.error(
                "candidate_writer_failed error=%s",
                exc,
            )

        finally:
            db.close()

        logger.info(
            "candidate_writer_complete inserted=%s updated=%s skipped=%s total=%s",
            inserted,
            updated,
            skipped,
            inserted + updated,
        )

        return inserted + updated

    # -----------------------------------------------------
    # BATCH PROCESS
    # -----------------------------------------------------

    def _process_batch(
        self,
        db,
        batch: List[Dict],
    ):

        inserted = 0
        updated = 0
        skipped = 0

        external_ids = [
            c.get("external_id")
            for c in batch
            if c.get("external_id")
        ]

        existing_map = {}

        if external_ids:
            stmt = select(DiscoveryCandidate).where(
                DiscoveryCandidate.external_id.in_(external_ids)
            )

            existing_rows = db.execute(stmt).scalars().all()

            existing_map = {
                row.external_id: row
                for row in existing_rows
            }

        for candidate in batch:

            try:

                external_id = _clean_str(candidate.get("external_id"))
                name = _clean_str(candidate.get("name"))
                city_id = _clean_str(candidate.get("city_id"))

                # 🔥 HARD GUARD (CRITICAL)
                if not name or not city_id:
                    skipped += 1
                    continue

                existing = existing_map.get(external_id) if external_id else None

                if existing:
                    self._update_candidate(existing, candidate)
                    updated += 1
                else:
                    obj = self._create_candidate(candidate)
                    db.add(obj)
                    inserted += 1

            except Exception as row_error:

                skipped += 1

                logger.debug(
                    "candidate_row_failed external_id=%s error=%s",
                    candidate.get("external_id"),
                    row_error,
                )

        return inserted, updated, skipped

    # -----------------------------------------------------
    # CREATE
    # -----------------------------------------------------

    def _create_candidate(
        self,
        candidate: Dict,
    ) -> DiscoveryCandidate:

        now = _now()

        lat = _safe_float(candidate.get("lat"))
        lng = _safe_float(candidate.get("lng") or candidate.get("lon"))

        return DiscoveryCandidate(
            external_id=_clean_str(candidate.get("external_id")),
            source=_clean_str(candidate.get("source")),
            name=_clean_str(candidate.get("name")),
            address=_clean_str(candidate.get("address")),
            city_id=_clean_str(candidate.get("city_id")),
            category_id=candidate.get("category_id"),
            lat=lat,
            lng=lng,
            phone=_clean_str(candidate.get("phone")),
            website=_clean_str(candidate.get("website")),
            raw_payload=candidate.get("raw_payload"),
            confidence_score=float(candidate.get("confidence", 0.0) or 0.0),
            created_at=now,
            updated_at=now,
        )

    # -----------------------------------------------------
    # UPDATE
    # -----------------------------------------------------

    def _update_candidate(
        self,
        obj: DiscoveryCandidate,
        candidate: Dict,
    ) -> None:

        name = _clean_str(candidate.get("name"))
        address = _clean_str(candidate.get("address"))
        phone = _clean_str(candidate.get("phone"))
        website = _clean_str(candidate.get("website"))

        lat = _safe_float(candidate.get("lat"))
        lng = _safe_float(candidate.get("lng") or candidate.get("lon"))

        if name:
            obj.name = name

        if address:
            obj.address = address

        if lat is not None:
            obj.lat = lat

        if lng is not None:
            obj.lng = lng

        if phone:
            obj.phone = phone

        if website:
            obj.website = website

        payload = candidate.get("raw_payload")

        if payload:
            obj.raw_payload = payload

        new_conf = candidate.get("confidence")

        if new_conf is not None:
            obj.confidence_score = max(
                float(obj.confidence_score or 0.0),
                float(new_conf),
            )

        obj.updated_at = _now()