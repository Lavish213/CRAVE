"""Preview or apply the reviewed disposition of Overture canary batch A.

The default mode is read-only. Applying requires an exact confirmation token
and refuses to proceed unless all ten immutable candidate identities and their
expected pre-review states still match production.

Usage::

    python scripts/apply_overture_entity_review.py
    python scripts/apply_overture_entity_review.py \
      --apply --confirm APPLY_OVERTURE_ENTITY_REVIEW
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.db.models.category import Category
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.discovery.promote_service_v2 import promote_candidate_v2


BATCH_ID = "oakland-20260830-a"
CONFIRMATION = "APPLY_OVERTURE_ENTITY_REVIEW"
SIMULATION_CONFIRMATION = "SIMULATE_OVERTURE_ENTITY_REVIEW"


@dataclass(frozen=True)
class Disposition:
    candidate_id: str
    external_id: str
    name: str
    action: str
    existing_place_id: str | None = None
    deactivate_place_id: str | None = None
    category_slug: str | None = None


DISPOSITIONS = (
    Disposition(
        "d770daaa-5585-4a4a-af04-55a4b649d3a6",
        "overture:800ada20-cac7-49f6-b40d-4c4a157f945c",
        "Forge Pizza",
        "reject_stale",
        deactivate_place_id="1e4a547c-e3f8-52dd-99bd-2c578d4cbdd3",
    ),
    Disposition(
        "da26f2ae-7f22-45de-85a5-817e10e4492f",
        "overture:ee8bf642-3ef7-4c08-b6f3-674c6dced662",
        "Good Vybes & Brews | Speciality Coffee and Tea",
        "match_existing",
        existing_place_id="d10b53b6-f3da-5e20-bbda-a4d36670262b",
    ),
    Disposition(
        "c5b9c338-1329-46fc-8ba9-a7b8c0bf1a19",
        "overture:1c7a700d-c403-4881-9b6d-ff28420735d1",
        "Miette",
        "reject_stale",
    ),
    Disposition(
        "4d451bf8-b7a9-4a17-acee-b9ea7a3dc2d8",
        "overture:fe1883f8-0a87-48c6-b06d-b52a5190122c",
        "Miss Pearl's Restaurant & Lounge",
        "reject_stale",
    ),
    Disposition(
        "cc0beb14-5fa8-4ecd-88a5-0eded5281aed",
        "overture:31f94772-8779-454f-b99f-e41d2eefe2f2",
        "NIDO Kitchen & Bar",
        "alias_existing",
        existing_place_id="2c1135b8-b42a-5877-9c3c-1380c35fe479",
        deactivate_place_id="5ca2b059-5eec-55d7-bf68-e713b639e3d1",
    ),
    Disposition(
        "724e210e-cb54-4d4a-a184-f3605b41b541",
        "overture:8d6e3921-d52c-4352-9051-de0142a47a13",
        "North Beach Sandwicheez",
        "promote_new",
        category_slug="american",
    ),
    Disposition(
        "864e7f2c-1616-45fe-9505-8a1092cdc440",
        "overture:47e8b665-886e-4f41-82c3-e51596a715e9",
        "Oakland United Beerworks",
        "match_existing",
        existing_place_id="e17f073f-19fb-5c5b-8206-2bc5d8140aab",
    ),
    Disposition(
        "01165936-c57e-49a1-b43d-bcfbcd4f8e93",
        "overture:91954b13-042a-4b24-8c5e-e49201a4ba34",
        "Odin",
        "match_existing",
        existing_place_id="2c1135b8-b42a-5877-9c3c-1380c35fe479",
    ),
    Disposition(
        "2b8a7725-fd96-4af3-9206-a446436955a6",
        "overture:2fa0e28c-6503-40b3-89a0-9e900b00cf23",
        "Tiger's Taproom",
        "reject_stale",
        deactivate_place_id="c6d7a916-0cde-508a-8074-3a85b79a70ce",
    ),
    Disposition(
        "5c2cec9e-6986-455f-845b-041495d06a8b",
        "overture:08523576-53af-4243-a2e5-28f774ab6f2b",
        "World Ground Cafe",
        "reject_stale",
    ),
)


def execution_is_authorized(*, apply: bool, confirmation: str | None) -> bool:
    return apply and confirmation == CONFIRMATION


def simulation_is_authorized(*, simulate: bool, confirmation: str | None) -> bool:
    return simulate and confirmation == SIMULATION_CONFIRMATION


def _batch_rows(db: Session) -> list[DiscoveryCandidate]:
    return (
        db.query(DiscoveryCandidate)
        .filter(
            DiscoveryCandidate.source == "overture",
            DiscoveryCandidate.raw_payload["canary_batch_id"].as_string() == BATCH_ID,
        )
        .all()
    )


def validate_batch(db: Session) -> dict[str, DiscoveryCandidate]:
    rows = _batch_rows(db)
    expected_ids = {item.candidate_id for item in DISPOSITIONS}
    actual_ids = {row.id for row in rows}
    if actual_ids != expected_ids:
        raise RuntimeError(
            f"batch identity changed: expected={sorted(expected_ids)} actual={sorted(actual_ids)}"
        )

    by_id = {row.id: row for row in rows}
    for item in DISPOSITIONS:
        row = by_id[item.candidate_id]
        if row.external_id != item.external_id or row.name != item.name:
            raise RuntimeError(f"candidate identity changed: {item.candidate_id}")
        if not row.blocked or row.resolved or row.resolved_place_id is not None:
            raise RuntimeError(f"candidate state changed: {item.candidate_id}")
        if item.existing_place_id and db.get(Place, item.existing_place_id) is None:
            raise RuntimeError(f"expected place missing: {item.existing_place_id}")
        if item.deactivate_place_id and db.get(Place, item.deactivate_place_id) is None:
            raise RuntimeError(f"stale place missing: {item.deactivate_place_id}")
    return by_id


def _mark_review(row: DiscoveryCandidate, *, action: str, evidence: str) -> None:
    payload = dict(row.raw_payload or {})
    payload.update(
        {
            "entity_review_action": action,
            "entity_review_evidence": evidence,
            "entity_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    row.raw_payload = payload


def apply_review(db: Session) -> dict:
    rows = validate_batch(db)
    summary = {"matched": 0, "aliases": 0, "rejected": 0, "promoted_new": 0, "deactivated": 0}

    for item in DISPOSITIONS:
        row = rows[item.candidate_id]
        if item.action == "match_existing":
            place = db.get(Place, item.existing_place_id)
            if not place.is_active:
                raise RuntimeError(f"reviewed existing place became inactive: {place.id}")
            if not place.address and row.address:
                place.address = row.address
            if not place.website and row.website:
                place.website = row.website
            row.resolved = True
            row.resolved_place_id = place.id
            row.status = "matched"
            _mark_review(row, action=item.action, evidence="verified current; exact existing entity")
            summary["matched"] += 1
        elif item.action == "alias_existing":
            row.resolved = True
            row.resolved_place_id = item.existing_place_id
            row.status = "alias"
            _mark_review(row, action=item.action, evidence="historical alias of verified current entity")
            summary["aliases"] += 1
        elif item.action == "reject_stale":
            row.resolved = True
            row.status = "rejected"
            _mark_review(row, action=item.action, evidence="verified closed, moved, or replaced")
            summary["rejected"] += 1
        elif item.action == "promote_new":
            category = (
                db.query(Category)
                .filter(Category.slug == item.category_slug, Category.is_active.is_(True))
                .one()
            )
            row.category_id = category.id
            place_id = promote_candidate_v2(db=db, candidate_id=row.id)
            if not place_id:
                raise RuntimeError(f"promotion failed for {row.name}")
            _mark_review(row, action=item.action, evidence="verified current and absent at this location")
            summary["promoted_new"] += 1
        else:
            raise RuntimeError(f"unknown disposition: {item.action}")

        if item.deactivate_place_id:
            stale = db.get(Place, item.deactivate_place_id)
            if stale.is_active:
                stale.is_active = False
                summary["deactivated"] += 1

        # Preserve the review barrier even after a row is resolved.
        row.blocked = True

    db.flush()
    return summary


def preview(db: Session) -> dict:
    validate_batch(db)
    return {
        "batch_id": BATCH_ID,
        "mode": "preview",
        "counts": {
            action: sum(item.action == action for item in DISPOSITIONS)
            for action in ("match_existing", "alias_existing", "reject_stale", "promote_new")
        },
        "deactivate_existing": sum(bool(item.deactivate_place_id) for item in DISPOSITIONS),
        "rows": [item.__dict__ for item in DISPOSITIONS],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()

    if args.apply and args.simulate:
        parser.error("choose either --apply or --simulate")

    db = SessionLocal()
    try:
        if not args.apply and not args.simulate:
            print(json.dumps(preview(db), indent=2))
            return 0
        if args.simulate:
            if not simulation_is_authorized(
                simulate=args.simulate,
                confirmation=args.confirm,
            ):
                parser.error(
                    f"simulation requires --confirm {SIMULATION_CONFIRMATION}"
                )
            result = apply_review(db)
            db.rollback()
            print(
                json.dumps(
                    {"batch_id": BATCH_ID, "mode": "simulated_rolled_back", **result},
                    indent=2,
                )
            )
            return 0
        if not execution_is_authorized(apply=args.apply, confirmation=args.confirm):
            parser.error(f"apply requires --confirm {CONFIRMATION}")
        result = apply_review(db)
        db.commit()
        print(json.dumps({"batch_id": BATCH_ID, "mode": "applied", **result}, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
