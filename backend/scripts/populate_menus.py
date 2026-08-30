"""Preview or run one bounded menu-population batch.

Preview is the default and performs no extraction or writes. Live execution
requires both ``--execute`` and the exact ``--confirm POPULATE`` sentinel.

Examples:
    python scripts/populate_menus.py --city-slug oakland --limit 10
    python scripts/populate_menus.py --city-slug oakland --limit 10 \
        --execute --confirm POPULATE
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError

from app.db.models.city import City
from app.db.session import SessionLocal
from app.services.workers.menu_worker import MAX_PLACES_PER_RUN, MenuWorker
from app.services.menu.source_quality import best_usable_source


def execution_is_authorized(*, execute: bool, confirmation: str | None) -> bool:
    return execute and confirmation == "POPULATE"


def _source_for(place) -> str | None:
    return best_usable_source(
        place.menu_source_url,
        place.grubhub_url,
        place.website,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-slug", help="Restrict the batch to one city.")
    parser.add_argument("--limit", type=int, default=10, help="1-100 places (default: 10).")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument("--execute", action="store_true", help="Actually run extraction.")
    parser.add_argument("--confirm", help="Must be exactly POPULATE with --execute.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    limit = max(1, min(100, args.limit))
    db = SessionLocal()
    try:
        try:
            city = None
            if args.city_slug:
                city = db.query(City).filter(City.slug == args.city_slug).one_or_none()
                if city is None:
                    print(f"No city found with slug={args.city_slug!r}", file=sys.stderr)
                    return 2

            worker = MenuWorker()
            candidates = worker._load_places_requiring_menu(
                db,
                city_id=city.id if city else None,
                limit=limit,
            )
        except SQLAlchemyError as exc:
            print(
                "Population preview failed: the configured database is unavailable or "
                "uninitialized. Set DATABASE_URL to a migrated CRAVE database first "
                f"({type(exc).__name__}).",
                file=sys.stderr,
            )
            return 2
        plan = {
            "mode": "execute" if args.execute else "preview",
            "city": city.slug if city else None,
            "requested_limit": limit,
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "id": place.id,
                    "name": place.name,
                    "source": _source_for(place),
                    "failure_count": place.menu_extraction_failure_count or 0,
                }
                for place in candidates
            ],
        }

        if args.json:
            print(json.dumps(plan, indent=2, sort_keys=True))
        else:
            print(
                f"Menu population {plan['mode']}: {len(candidates)} candidate(s) "
                f"for {city.slug if city else 'all active cities'}"
            )
            for candidate in plan["candidates"]:
                print(
                    f"- {candidate['name']} [{candidate['id']}] "
                    f"failures={candidate['failure_count']} source={candidate['source']}"
                )

        if not args.execute:
            print("Preview only; no extraction or database writes were performed.")
            return 0

        if not execution_is_authorized(execute=args.execute, confirmation=args.confirm):
            print(
                "Execution refused: add --confirm POPULATE after reviewing the preview.",
                file=sys.stderr,
            )
            return 2
    finally:
        db.close()

    summary = MenuWorker().run(
        max_places=min(limit, MAX_PLACES_PER_RUN),
        city_id=city.id if city else None,
    )
    print(json.dumps({"population_summary": summary}, sort_keys=True))
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
