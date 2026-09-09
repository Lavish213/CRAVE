"""
Backfill hours/outdoor_seating claims for already-promoted OSM places.

app.services.discovery.osm_overpass.fetch_osm_pois has always stored the
entire OSM tags dict verbatim on DiscoveryCandidate.raw_payload -- so
opening_hours and outdoor_seating have been sitting in Postgres, unread,
for every OSM-sourced candidate ever ingested, including ones already
promoted to a Place long before promote_service_v2.py learned to read
these two tags (see that module's _osm_tag_claims). This script re-reads
that already-stored raw_payload for already-promoted candidates and
writes the claims retroactively -- no new network fetch, no re-scrape,
free and instant against data already sitting in this database.

Idempotent: skips a candidate whose claim (by its deterministic
claim_key) already exists, so this is safe to re-run after a fresh
osm ingest/promote cycle picks up newer candidates naturally through
promote_service_v2.py's own normal path.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place_claim import PlaceClaim
from app.services.discovery.promote_service_v2 import _osm_tag_claims
from app.services.truth.truth_resolver_v2 import resolve_place_truths_v2

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

BATCH = 500

_CLAIM_FIELDS = {
    "field", "value_text", "value_number", "value_json",
    "source", "confidence", "weight", "claim_key",
    "is_user_submitted", "is_verified_source",
}


def _candidates_to_backfill(db: Session):
    return (
        db.query(DiscoveryCandidate)
        .filter(
            DiscoveryCandidate.source == "osm",
            DiscoveryCandidate.resolved_place_id.is_not(None),
            DiscoveryCandidate.raw_payload.is_not(None),
        )
        .all()
    )


def run_backfill(*, dry_run: bool = False) -> dict:
    db = SessionLocal()
    claims_written = 0
    candidates_touched = 0
    affected_place_ids: set[str] = set()
    scheduled_claim_keys: set[tuple[str, str, str]] = set()

    try:
        candidates = _candidates_to_backfill(db)
        logger.info("osm_candidates_scanned=%s", len(candidates))

        for i in range(0, len(candidates), BATCH):
            batch = candidates[i:i + BATCH]
            batch_affected_place_ids: set[str] = set()

            for candidate in batch:
                place_id = candidate.resolved_place_id
                new_claims = _osm_tag_claims(candidate)
                if not new_claims:
                    continue

                wrote_any = False
                for c in new_claims:
                    claim_identity = (place_id, c["field"], c["claim_key"])
                    if claim_identity in scheduled_claim_keys:
                        continue

                    existing = (
                        db.query(PlaceClaim)
                        .filter(
                            PlaceClaim.place_id == place_id,
                            PlaceClaim.field == c["field"],
                            PlaceClaim.claim_key == c["claim_key"],
                        )
                        .one_or_none()
                    )
                    if existing:
                        continue

                    scheduled_claim_keys.add(claim_identity)
                    if not dry_run:
                        db.add(PlaceClaim(
                            place_id=place_id,
                            **{k: v for k, v in c.items() if k in _CLAIM_FIELDS},
                        ))
                    claims_written += 1
                    wrote_any = True

                if wrote_any:
                    candidates_touched += 1
                    batch_affected_place_ids.add(place_id)

            if not dry_run:
                db.flush()
                for place_id in batch_affected_place_ids:
                    resolve_place_truths_v2(db=db, place_id=place_id)
                db.commit()

            affected_place_ids.update(batch_affected_place_ids)

            logger.info(
                "progress: scanned=%s claims_written=%s places_affected=%s",
                i + len(batch), claims_written, len(affected_place_ids),
            )

        logger.info(
            "backfill_done: candidates_touched=%s claims_written=%s places_affected=%s dry_run=%s",
            candidates_touched, claims_written, len(affected_place_ids), dry_run,
        )

        return {
            "candidates_touched": candidates_touched,
            "claims_written": claims_written,
            "places_affected": len(affected_place_ids),
        }
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    run_backfill(dry_run="--dry-run" in sys.argv)
