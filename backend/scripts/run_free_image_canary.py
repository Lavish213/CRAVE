"""Stage a bounded, exact-target free-image acquisition canary.

This is deliberately separate from the recurring ``image_ingestion`` job:

* callers name every place ID;
* preview is the default;
* execution requires an exact confirmation count;
* places with any existing image row are refused to keep rollback trivial;
* only provider claims and the official website are read;
* Google is structurally unreachable; and
* newly written rows are staged as hidden/non-primary for review.

Examples::

    python scripts/run_free_image_canary.py --place-ids id-1,id-2
    python scripts/run_free_image_canary.py --place-ids id-1,id-2 \
        --run --confirm-count 2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage, VISIBILITY_HIDDEN
from app.db.session import SessionLocal
from app.services.images.image_ingest_service import ImageIngestService
from app.services.images.image_reader import ImageReader


MAX_CANARY_PLACES = 10


class FreeOnlyImageReader(ImageReader):
    """ImageReader variant whose control flow contains no Google branch."""

    def read(self, *, place: Place, db=None) -> list[dict]:
        candidates = []
        candidates.extend(self._read_provider(place))
        candidates.extend(self._read_website(place, db=db))
        return self._normalize_candidates(place=place, candidates=candidates)

    def _read_google(self, place: Place) -> list[dict]:  # pragma: no cover
        raise AssertionError("Google must be unreachable in the free-image canary")


def parse_place_ids(raw: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in raw.replace(",", "\n").splitlines():
        place_id = value.strip()
        if place_id and place_id not in seen:
            seen.add(place_id)
            result.append(place_id)
    return result


def run_is_authorized(*, requested_count: int, confirm_count: int | None) -> bool:
    return confirm_count is not None and confirm_count == requested_count


def build_preview(db, place_ids: list[str]) -> tuple[dict, list[dict], dict[str, Place]]:
    places = db.query(Place).filter(Place.id.in_(place_ids)).all()
    places_by_id = {place.id: place for place in places}
    rows: list[dict] = []
    for place_id in place_ids:
        place = places_by_id.get(place_id)
        if place is None:
            rows.append({"place_id": place_id, "found": False})
            continue
        image_count = db.query(PlaceImage).filter(PlaceImage.place_id == place_id).count()
        rows.append(
            {
                "place_id": place_id,
                "found": True,
                "name": place.name,
                "is_active": bool(place.is_active),
                "website": place.website,
                "menu_source_url": place.menu_source_url,
                "grubhub_url": place.grubhub_url,
                "existing_image_rows": image_count,
            }
        )

    missing = [row["place_id"] for row in rows if not row["found"]]
    inactive = [row["place_id"] for row in rows if row.get("found") and not row["is_active"]]
    existing = [row["place_id"] for row in rows if row.get("existing_image_rows", 0) > 0]
    return (
        {
            "mode": "preview",
            "requested": len(place_ids),
            "found": len(place_ids) - len(missing),
            "missing": missing,
            "inactive": inactive,
            "already_has_image_rows": existing,
        },
        rows,
        places_by_id,
    )


def stage_canary(db, *, place_ids: list[str], places_by_id: dict[str, Place]) -> tuple[list[dict], dict]:
    service = ImageIngestService(reader=FreeOnlyImageReader())
    results: list[dict] = []
    total_staged = 0

    for place_id in place_ids:
        place = places_by_id[place_id]
        before_ids = {
            row[0]
            for row in db.query(PlaceImage.id).filter(PlaceImage.place_id == place_id).all()
        }
        images = service.ingest_place_images(db=db, place=place, force_refresh=False)
        db.flush()
        new_images = [image for image in images if image.id not in before_ids]

        for image in new_images:
            image.visibility_status = VISIBILITY_HIDDEN
            image.is_primary = False
        db.commit()

        total_staged += len(new_images)
        results.append(
            {
                "place_id": place_id,
                "name": place.name,
                "staged": len(new_images),
                "images": [
                    {
                        "id": image.id,
                        "url": image.url,
                        "visibility_status": image.visibility_status,
                        "is_primary": image.is_primary,
                    }
                    for image in new_images
                ],
            }
        )

    return results, {"attempted": len(place_ids), "staged": total_staged, "publicly_visible": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-ids", required=True, help="Comma- or newline-separated exact place IDs")
    parser.add_argument("--run", action="store_true", help="Stage candidates (default is preview)")
    parser.add_argument("--confirm-count", type=int, help="Must exactly equal the de-duplicated ID count")
    args = parser.parse_args(argv)

    place_ids = parse_place_ids(args.place_ids)
    if not place_ids or len(place_ids) > MAX_CANARY_PLACES:
        print(f"Refused: give 1-{MAX_CANARY_PLACES} exact place IDs.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        summary, rows, places_by_id = build_preview(db, place_ids)
        output: dict = {"canary_summary": summary, "places": rows}
        if not args.run:
            print(json.dumps(output, indent=2, sort_keys=True, default=str))
            return 0
        if not run_is_authorized(requested_count=len(place_ids), confirm_count=args.confirm_count):
            print(
                f"Run refused: --confirm-count must exactly equal {len(place_ids)}.",
                file=sys.stderr,
            )
            return 2
        if summary["missing"] or summary["inactive"] or summary["already_has_image_rows"]:
            print(f"Run refused due to preview blockers: {summary}", file=sys.stderr)
            return 2

        results, run_summary = stage_canary(db, place_ids=place_ids, places_by_id=places_by_id)
        output["canary_summary"]["mode"] = "run"
        output["run_summary"] = run_summary
        output["results"] = results
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
