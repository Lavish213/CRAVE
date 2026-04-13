from __future__ import annotations

import json
import logging
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models.place import Place

from app.services.ingest.toast_browser_scraper import fetch_toast_data
from app.services.ingest.toast_ingest import (
    ingest_toast_json_strings,
    ToastRestaurantInput,
)

from app.services.ingest.toast_menu_extractor import extract_menu_from_toast_payloads
from app.services.menu.menu_writer import MenuWriter


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -----------------------------------------------------
# PLACE RESOLUTION
# -----------------------------------------------------

def _find_place(db, url: str, name_hint: str | None) -> Place | None:

    # 1. match by website
    stmt = select(Place).where(
        Place.website.ilike(f"%{url.split('/v3')[0]}%")
    )

    place = db.execute(stmt).scalar_one_or_none()

    if place:
        return place

    # 2. fallback by name
    if name_hint:
        stmt = select(Place).where(
            Place.name.ilike(f"%{name_hint}%")
        )
        return db.execute(stmt).scalar_one_or_none()

    return None


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------

def run(url: str, city_id: str):

    logger.info("toast_run_start url=%s city_id=%s", url, city_id)

    # ----------------------------------------
    # STEP 1: SCRAPE
    # ----------------------------------------
    payloads = fetch_toast_data(url)

    if not payloads:
        logger.error("toast_run_no_payloads")
        raise SystemExit(1)

    payload_strings = [json.dumps(p) for p in payloads]

    logger.info("toast_payloads count=%s", len(payloads))

    # ----------------------------------------
    # STEP 2: CANDIDATE INGEST (DISCOVERY)
    # ----------------------------------------
    result = ingest_toast_json_strings(
        db=None,
        restaurant_input=ToastRestaurantInput(
            city_id=city_id,
            source_url=url,
        ),
        payload_strings=payload_strings,
    )

    logger.info(
        "toast_candidate_ingest restaurant=%s items=%s written=%s",
        result.restaurant_name,
        result.item_count,
        result.written_count,
    )

    # ----------------------------------------
    # STEP 3: MENU EXTRACTION (NEW PIPELINE)
    # ----------------------------------------
    items = extract_menu_from_toast_payloads(payloads)

    logger.info("toast_menu_extracted items=%s", len(items))

    if not items:
        logger.warning("toast_menu_empty")
        return

    # ----------------------------------------
    # STEP 4: FIND PLACE
    # ----------------------------------------
    db = SessionLocal()

    try:
        place = _find_place(
            db,
            url=url,
            name_hint=result.restaurant_name,
        )

        if not place:
            logger.warning("toast_place_not_found")
            return

        logger.info(
            "toast_place_resolved id=%s name=%s",
            place.id,
            place.name,
        )

        # ----------------------------------------
        # STEP 5: WRITE MENU (CRITICAL)
        # ----------------------------------------
        writer = MenuWriter()

        inserted = writer.write(
            place_id=place.id,
            items=items,
        )

        logger.info(
            "toast_menu_written place_id=%s items=%s",
            place.id,
            inserted,
        )

    finally:
        db.close()

    # ----------------------------------------
    # FINAL OUTPUT
    # ----------------------------------------
    print("\n=== RESULT ===")
    print(f"Restaurant: {result.restaurant_name}")
    print(f"Candidates: {result.item_count}")
    print(f"Menu Items Written: {len(items)}")
    print()


# -----------------------------------------------------
# ENTRYPOINT
# -----------------------------------------------------

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("Usage: python run_toast_ingest.py <toast_url> <city_id>")
        sys.exit(1)

    toast_url = sys.argv[1]
    city_id = sys.argv[2]

    run(toast_url, city_id)