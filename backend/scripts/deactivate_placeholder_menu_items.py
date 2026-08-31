"""Safely deactivate unmistakable placeholder menu rows.

The normal publisher now refuses these rows, but legacy rows can remain active
until their place is republished. This maintenance command uses the publisher's
exact predicate so detection cannot drift.

Preview (default):
    python scripts/deactivate_placeholder_menu_items.py

Transactional simulation:
    python scripts/deactivate_placeholder_menu_items.py \
        --simulate --confirm SIMULATE_PLACEHOLDER_MENU_CLEANUP

Apply after reviewing the printed IDs:
    python scripts/deactivate_placeholder_menu_items.py \
        --apply --confirm APPLY_PLACEHOLDER_MENU_CLEANUP
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.db.models.menu_item import MenuItem
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.menu.menu_publisher import is_obvious_placeholder_item


APPLY_CONFIRMATION = "APPLY_PLACEHOLDER_MENU_CLEANUP"
SIMULATE_CONFIRMATION = "SIMULATE_PLACEHOLDER_MENU_CLEANUP"


@dataclass(frozen=True)
class Finding:
    menu_item_id: str
    place_id: str
    place_name: str
    item_name: str
    price_cents: int | None


def execution_is_authorized(*, apply: bool, confirmation: str | None) -> bool:
    return apply and confirmation == APPLY_CONFIRMATION


def simulation_is_authorized(*, simulate: bool, confirmation: str | None) -> bool:
    return simulate and confirmation == SIMULATE_CONFIRMATION


def find_active_placeholders(db: Session) -> list[tuple[MenuItem, Place]]:
    # The deliberately broad SQL prefilter keeps this bounded; the exact,
    # conservative publisher predicate makes the final decision.
    candidates = (
        db.query(MenuItem, Place)
        .join(Place, Place.id == MenuItem.place_id)
        .filter(MenuItem.is_active.is_(True))
        .filter(MenuItem.name.ilike("%test%") | MenuItem.name.ilike("%mock%") |
                MenuItem.name.ilike("%placeholder%") | MenuItem.name.ilike("%dummy%") |
                MenuItem.name.ilike("%fake%"))
        .order_by(MenuItem.id.asc())
        .all()
    )
    return [
        (item, place)
        for item, place in candidates
        if is_obvious_placeholder_item(
            name=item.name,
            price_cents=item.price_cents,
            description=item.description,
        )
    ]


def deactivate(db: Session) -> list[Finding]:
    findings: list[Finding] = []
    for item, place in find_active_placeholders(db):
        findings.append(Finding(
            menu_item_id=item.id,
            place_id=place.id,
            place_name=place.name,
            item_name=item.name,
            price_cents=item.price_cents,
        ))
        item.is_active = False
    db.flush()
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--simulate", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()

    if args.apply and not execution_is_authorized(
        apply=args.apply, confirmation=args.confirm
    ):
        parser.error(f"apply requires --confirm {APPLY_CONFIRMATION}")
    if args.simulate and not simulation_is_authorized(
        simulate=args.simulate, confirmation=args.confirm
    ):
        parser.error(f"simulation requires --confirm {SIMULATE_CONFIRMATION}")

    db = SessionLocal()
    try:
        if not args.apply and not args.simulate:
            rows = [
                Finding(item.id, place.id, place.name, item.name, item.price_cents)
                for item, place in find_active_placeholders(db)
            ]
            print(json.dumps({"mode": "preview", "count": len(rows),
                              "findings": [asdict(row) for row in rows]}, indent=2))
            return

        rows = deactivate(db)
        if args.simulate:
            db.rollback()
            mode_name = "simulated_rolled_back"
        else:
            db.commit()
            mode_name = "applied"
        print(json.dumps({"mode": mode_name, "count": len(rows),
                          "findings": [asdict(row) for row in rows]}, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
