"""
Preview or run a bounded, exact-target menu-extraction canary against a
specific, named list of place IDs -- never a discovered/ranked selection.

The existing scheduler job (menu_worker.py, via app.scheduler) and its
manual-run wrapper (scripts/run_menu_worker.py) both select places
themselves out of the full backlog (highest rank_score first, oldest-
attempted-first within backoff rules) -- correct for routine, ongoing
enrichment, but the wrong shape for a first bounded canary against a
backlog that has never been run: nobody has reviewed which specific
places get touched, there's no preview step, and there's no way to
confirm you actually ran against exactly the N places you intended
rather than however many an unreviewed query happened to return.

This tool never selects places on its own -- you name the exact IDs,
same discipline as the Overture population canary
(scripts/run_overture_canary.py): preview-by-default, an exact
confirmation gate to actually execute, and per-place output so the
result set is fully auditable afterward.

What this does NOT do: automated rollback of a materialized menu.
Unlike the Overture canary (which stages blocked candidate rows that
are trivial to delete before promotion), a materialized menu already
went through materialize_menu_truth -> MenuPublisher, the same
established pipeline every scraped source uses -- reverting it means
deleting specific PlaceClaim/PlaceTruth/MenuItem rows and resetting
Place.has_menu, which this tool deliberately does not attempt
automatically. Every result row below prints exactly which place_ids
were touched and how, so a manual rollback (if ever needed) has an
exact, reviewable list to work from.

Examples::

    python scripts/run_menu_backlog_canary.py --place-ids-file canary.txt
    python scripts/run_menu_backlog_canary.py --place-ids-file canary.txt \
        --run --confirm-count 25
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.workers.menu_worker import MenuWorker


MAX_CANARY_PLACES = 100


def parse_place_ids(raw: str) -> list[str]:
    """Comma- or newline-separated -> a de-duplicated, order-preserved list.

    De-duping matters here specifically because the result feeds
    --confirm-count: a repeated ID in the input must not be attempted
    twice, and must not silently inflate the count a caller has to match.
    """
    ids = [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]
    seen: set[str] = set()
    deduped: list[str] = []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            deduped.append(pid)
    return deduped


def run_is_authorized(*, requested_count: int, confirm_count: int | None) -> bool:
    """--confirm-count must exactly equal the number of place IDs given --
    deliberate friction forcing the caller to have actually counted what
    they're about to run, same shape as the Overture canary's
    execution_is_authorized()."""
    return confirm_count is not None and confirm_count == requested_count


def _preview_row(place: Place | None, place_id: str) -> dict:
    if place is None:
        return {"place_id": place_id, "found": False}
    return {
        "place_id": place.id,
        "found": True,
        "name": place.name,
        "city_id": place.city_id,
        "is_active": place.is_active,
        "has_menu": bool(place.has_menu),
        "website": place.website,
        "menu_source_url": place.menu_source_url,
        "grubhub_url": place.grubhub_url,
        "menu_extraction_failure_count": place.menu_extraction_failure_count or 0,
        "menu_extraction_attempted_at": (
            place.menu_extraction_attempted_at.isoformat()
            if place.menu_extraction_attempted_at else None
        ),
    }


def build_preview(db, place_ids: list[str]) -> tuple[dict, list[dict], dict[str, Place]]:
    places_by_id = {
        p.id: p
        for p in db.query(Place).filter(Place.id.in_(place_ids)).all()
    }
    preview = [_preview_row(places_by_id.get(pid), pid) for pid in place_ids]
    missing = [row["place_id"] for row in preview if not row["found"]]
    inactive = [row["place_id"] for row in preview if row["found"] and not row["is_active"]]

    summary = {
        "mode": "preview",
        "requested": len(place_ids),
        "found": len(place_ids) - len(missing),
        "missing": missing,
        "inactive": inactive,
    }
    return summary, preview, places_by_id


def run_canary(db, *, place_ids: list[str], places_by_id: dict[str, Place]) -> tuple[list[dict], dict]:
    """Runs extraction for exactly the given place_ids (already validated
    present and active by the caller) via MenuWorker's own per-place
    logic, then a single batched recompute for whatever materialized --
    same reuse-tested-code discipline as menu_worker.py itself."""
    worker = MenuWorker()
    results = []
    materialized_places = []
    for pid in place_ids:
        place = places_by_id[pid]
        outcome = worker._process_one_place(db, place)
        results.append({"place_id": pid, "name": place.name, **outcome})
        if outcome["materialized"]:
            materialized_places.append(place)

    recompute_warning = None
    if materialized_places:
        from app.workers.recompute_scores_worker import recompute_places_v4
        try:
            recompute_places_v4(db, places=materialized_places)
            db.commit()
        except Exception as exc:
            db.rollback()
            recompute_warning = (
                f"score recompute failed after extraction ({exc}) -- "
                f"extraction itself was already committed per-place above, "
                f"scores will pick this up on the next scheduled recompute pass."
            )

    run_summary = {
        "attempted": len(results),
        "materialized": sum(1 for r in results if r["materialized"]),
        "no_menu": sum(1 for r in results if not r["materialized"] and not r["error"]),
        "errors": sum(1 for r in results if r["error"]),
    }
    if recompute_warning:
        run_summary["recompute_warning"] = recompute_warning
    return results, run_summary


def _read_place_ids_from_args(args: argparse.Namespace) -> list[str]:
    if args.place_ids:
        raw = args.place_ids
    elif args.place_ids_file:
        raw = Path(args.place_ids_file).read_text()
    else:
        raise SystemExit("Provide --place-ids or --place-ids-file.")
    return parse_place_ids(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-ids", help="Comma- or newline-separated exact place IDs")
    parser.add_argument("--place-ids-file", help="Path to a file with one place ID per line")
    parser.add_argument("--run", action="store_true", help="Actually execute (default is preview-only)")
    parser.add_argument("--confirm-count", type=int, help="Must exactly equal the number of place IDs given")
    args = parser.parse_args(argv)

    place_ids = _read_place_ids_from_args(args)
    if not place_ids:
        print("No place IDs given.", file=sys.stderr)
        return 2
    if len(place_ids) > MAX_CANARY_PLACES:
        print(
            f"Refused: {len(place_ids)} place IDs given, this tool caps a "
            f"single canary run at {MAX_CANARY_PLACES}. Run it in smaller "
            f"batches.",
            file=sys.stderr,
        )
        return 2

    db = SessionLocal()
    try:
        summary, preview, places_by_id = build_preview(db, place_ids)
        output: dict = {"canary_summary": summary, "places": preview}

        if not args.run:
            print(json.dumps(output, indent=2, sort_keys=True, default=str))
            return 0

        if not run_is_authorized(requested_count=len(place_ids), confirm_count=args.confirm_count):
            print(
                f"Run refused: --confirm-count must exactly equal the number "
                f"of place IDs given ({len(place_ids)}). Got "
                f"{args.confirm_count!r}. This is deliberate friction -- it "
                f"forces you to have actually counted what you're about to run.",
                file=sys.stderr,
            )
            return 2
        if summary["missing"]:
            print(
                f"Run refused: {len(summary['missing'])} place ID(s) not "
                f"found: {summary['missing']}. Fix the input list before "
                f"running -- this tool never silently skips a place you named.",
                file=sys.stderr,
            )
            return 2
        if summary["inactive"]:
            print(
                f"Run refused: {len(summary['inactive'])} place ID(s) are "
                f"not active: {summary['inactive']}. Extracting a menu for "
                f"an inactive place is not a meaningful canary result.",
                file=sys.stderr,
            )
            return 2

        results, run_summary = run_canary(db, place_ids=place_ids, places_by_id=places_by_id)
        output["run_summary"] = run_summary
        output["canary_summary"]["mode"] = "run"
        output["results"] = results

        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
