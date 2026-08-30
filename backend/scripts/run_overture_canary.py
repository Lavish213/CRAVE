"""Preview, stage, or roll back a bounded Overture population canary.

The default mode is read-only. Staged rows are always created as blocked
``DiscoveryCandidate`` records, so the five-minute promotion worker cannot
make them user-visible before review. A batch can be removed only while every
row is still blocked and unresolved.

Examples::

    python scripts/run_overture_canary.py --city-slug oakland --limit 10
    python scripts/run_overture_canary.py --city-slug oakland --limit 10 \
        --stage --batch-id oakland-20260830-a --confirm STAGE_OVERTURE
    python scripts/run_overture_canary.py \
        --rollback-batch oakland-20260830-a --confirm ROLLBACK_OVERTURE
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models.city import City
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.discovery.overture_places import fetch_overture_places


MAX_STAGE_LIMIT = 100
DEFAULT_BBOX_DEGREES = 0.01
STAGE_CONFIRMATION = "STAGE_OVERTURE"
ROLLBACK_CONFIRMATION = "ROLLBACK_OVERTURE"
CANARY_MARKER = "overture_population_canary"
NEAR_DUPLICATE_METERS = 100.0


@dataclass(frozen=True)
class NearbyAssessment:
    nearest_place_id: str | None
    nearest_place_name: str | None
    nearest_distance_m: float | None
    same_name_within_100m: bool
    likely_duplicate_within_100m: bool


def _normalized_name(value: str | None) -> str:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return haversine distance in meters for audit classification."""
    radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _names_likely_match(left: str | None, right: str | None) -> bool:
    """Conservative audit heuristic; never used to merge records."""
    left_name = _normalized_name(left)
    right_name = _normalized_name(right)
    if not left_name or not right_name:
        return False
    if left_name == right_name:
        return True
    left_tokens = set(left_name.split())
    right_tokens = set(right_name.split())
    shorter = min(len(left_tokens), len(right_tokens))
    token_overlap = len(left_tokens & right_tokens) / shorter if shorter else 0.0
    return token_overlap >= 0.8 or SequenceMatcher(None, left_name, right_name).ratio() >= 0.78


def _assess_nearby(record: dict, places: Iterable[Place]) -> NearbyAssessment:
    nearest: Place | None = None
    nearest_distance: float | None = None
    record_name = _normalized_name(record.get("name"))

    for place in places:
        if place.lat is None or place.lng is None:
            continue
        distance = _distance_m(
            float(record["lat"]),
            float(record["lon"]),
            float(place.lat),
            float(place.lng),
        )
        if nearest_distance is None or distance < nearest_distance:
            nearest = place
            nearest_distance = distance

    same_name_nearby = bool(
        nearest
        and nearest_distance is not None
        and nearest_distance <= NEAR_DUPLICATE_METERS
        and _normalized_name(nearest.name) == record_name
    )
    likely_duplicate = bool(
        nearest
        and nearest_distance is not None
        and nearest_distance <= NEAR_DUPLICATE_METERS
        and _names_likely_match(nearest.name, record.get("name"))
    )
    return NearbyAssessment(
        nearest_place_id=nearest.id if nearest else None,
        nearest_place_name=nearest.name if nearest else None,
        nearest_distance_m=round(nearest_distance, 1) if nearest_distance is not None else None,
        same_name_within_100m=same_name_nearby,
        likely_duplicate_within_100m=likely_duplicate,
    )


def execution_is_authorized(*, stage: bool, confirmation: str | None) -> bool:
    return stage and confirmation == STAGE_CONFIRMATION


def rollback_is_authorized(*, batch_id: str | None, confirmation: str | None) -> bool:
    return bool(batch_id) and confirmation == ROLLBACK_CONFIRMATION


def _fetch_for_city(city: City, bbox_degrees: float) -> list[dict]:
    return fetch_overture_places(
        lat_min=float(city.lat) - bbox_degrees,
        lat_max=float(city.lat) + bbox_degrees,
        lon_min=float(city.lng) - bbox_degrees,
        lon_max=float(city.lng) + bbox_degrees,
    )


def _existing_external_ids(db, records: list[dict]) -> set[str]:
    external_ids = [record["external_id"] for record in records if record.get("external_id")]
    if not external_ids:
        return set()
    rows = (
        db.query(DiscoveryCandidate.external_id)
        .filter(
            DiscoveryCandidate.source == "overture",
            DiscoveryCandidate.external_id.in_(external_ids),
        )
        .all()
    )
    return {row[0] for row in rows}


def _plan(
    db,
    *,
    city: City,
    records: list[dict],
    limit: int,
) -> tuple[dict, list[dict], list[dict]]:
    existing_ids = _existing_external_ids(db, records)
    city_places = (
        db.query(Place)
        .filter(Place.city_id == city.id, Place.is_active.is_(True))
        .all()
    )
    new_records = [
        record for record in records
        if record.get("external_id") and record["external_id"] not in existing_ids
    ]
    selected = new_records[:limit]
    samples = []
    near_duplicate_count = 0
    likely_duplicate_count = 0
    for record in selected:
        assessment = _assess_nearby(record, city_places)
        near_duplicate_count += int(assessment.same_name_within_100m)
        likely_duplicate_count += int(assessment.likely_duplicate_within_100m)
        samples.append({
            "external_id": record["external_id"],
            "name": record["name"],
            "address": record.get("address"),
            "website": record.get("website"),
            "category_hint": record.get("category_hint"),
            "nearest_place_id": assessment.nearest_place_id,
            "nearest_place_name": assessment.nearest_place_name,
            "nearest_distance_m": assessment.nearest_distance_m,
            "same_name_within_100m": assessment.same_name_within_100m,
            "likely_duplicate_within_100m": assessment.likely_duplicate_within_100m,
        })

    summary = {
        "mode": "preview",
        "city": city.slug,
        "fetched": len(records),
        "already_staged": len(existing_ids),
        "new_source_records": len(new_records),
        "selected": len(selected),
        "selected_with_address": sum(bool(record.get("address")) for record in selected),
        "selected_with_website": sum(bool(record.get("website")) for record in selected),
        "selected_with_category": sum(bool(record.get("category_hint")) for record in selected),
        "selected_same_name_within_100m": near_duplicate_count,
        "selected_likely_duplicate_within_100m": likely_duplicate_count,
    }
    return summary, selected, samples


def _stage(db, *, city: City, records: list[dict], batch_id: str) -> dict:
    inserted = 0
    skipped_conflict = 0
    for record in records:
        raw_payload = dict(record.get("raw_payload") or {})
        raw_payload.update({
            "canary_marker": CANARY_MARKER,
            "canary_batch_id": batch_id,
        })
        candidate = DiscoveryCandidate(
            external_id=record["external_id"],
            source="overture",
            name=record["name"],
            city_id=city.id,
            lat=record.get("lat"),
            lng=record.get("lon"),
            address=record.get("address"),
            phone=record.get("phone"),
            website=record.get("website"),
            category_hint=record.get("category_hint"),
            confidence_score=float(record.get("confidence") or 0.0),
            raw_payload=raw_payload,
            status="candidate",
            resolved=False,
            blocked=True,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            inserted += 1
        except IntegrityError:
            skipped_conflict += 1
    db.commit()
    return {
        "batch_id": batch_id,
        "inserted_blocked": inserted,
        "skipped_conflict": skipped_conflict,
    }


def _rollback(db, batch_id: str) -> dict:
    query = _batch_query(db, batch_id).filter(
        DiscoveryCandidate.blocked.is_(True),
        DiscoveryCandidate.resolved.is_(False),
        DiscoveryCandidate.resolved_place_id.is_(None),
    )
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return {"batch_id": batch_id, "rolled_back": count}


def _batch_query(db, batch_id: str):
    return db.query(DiscoveryCandidate).filter(
        DiscoveryCandidate.source == "overture",
        DiscoveryCandidate.raw_payload["canary_marker"].as_string() == CANARY_MARKER,
        DiscoveryCandidate.raw_payload["canary_batch_id"].as_string() == batch_id,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-slug", default="oakland")
    parser.add_argument("--bbox-degrees", type=float, default=DEFAULT_BBOX_DEGREES)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--stage", action="store_true")
    parser.add_argument("--batch-id")
    parser.add_argument("--rollback-batch")
    parser.add_argument("--confirm")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    limit = max(1, min(MAX_STAGE_LIMIT, args.limit))
    db = SessionLocal()
    try:
        if args.rollback_batch:
            if not rollback_is_authorized(
                batch_id=args.rollback_batch,
                confirmation=args.confirm,
            ):
                print("Rollback refused: add --confirm ROLLBACK_OVERTURE.", file=sys.stderr)
                return 2
            result = _rollback(db, args.rollback_batch)
            print(json.dumps({"rollback_summary": result}, indent=2, sort_keys=True))
            return 0

        city = db.query(City).filter(
            City.slug == args.city_slug,
            City.is_active.is_(True),
        ).one_or_none()
        if city is None or city.lat is None or city.lng is None:
            print(f"Active geocoded city not found: {args.city_slug!r}", file=sys.stderr)
            return 2

        records = _fetch_for_city(city, max(0.001, min(0.08, args.bbox_degrees)))
        summary, selected, samples = _plan(db, city=city, records=records, limit=limit)
        output = {"canary_summary": summary, "selected_records": samples}

        if args.stage:
            if not args.batch_id:
                print("Staging refused: --batch-id is required.", file=sys.stderr)
                return 2
            if not execution_is_authorized(stage=True, confirmation=args.confirm):
                print("Staging refused: add --confirm STAGE_OVERTURE.", file=sys.stderr)
                return 2
            existing_batch_rows = _batch_query(db, args.batch_id).count()
            if existing_batch_rows:
                print(
                    f"Staging refused: batch {args.batch_id!r} already has "
                    f"{existing_batch_rows} row(s). Use a new batch ID.",
                    file=sys.stderr,
                )
                return 2
            output["stage_summary"] = _stage(
                db,
                city=city,
                records=selected,
                batch_id=args.batch_id,
            )
            output["canary_summary"]["mode"] = "stage"

        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
