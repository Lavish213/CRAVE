#!/usr/bin/env python3
"""
Data validation script.

Checks the health of the CRAVE backend data and prints a summary report.

Usage:
    python scripts/run_data_validation.py
"""
from __future__ import annotations

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func, and_

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth


logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def _count(db, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    for cond in conditions:
        stmt = stmt.where(cond)
    return db.execute(stmt).scalar_one()


def run() -> dict:
    db = SessionLocal()
    try:
        # --- Place counts ---
        total_places = _count(db, Place)
        active_places = _count(db, Place, Place.is_active.is_(True))
        inactive_places = total_places - active_places

        places_with_menu = _count(db, Place, Place.has_menu.is_(True))
        places_no_geo = _count(
            db, Place,
            Place.is_active.is_(True),
            Place.lat.is_(None),
        )
        places_no_name = _count(
            db, Place,
            Place.name.is_(None),
        )
        places_no_score = _count(
            db, Place,
            Place.is_active.is_(True),
            Place.master_score.is_(None),
        )

        # --- Claims ---
        total_claims = _count(db, PlaceClaim)

        # --- Truths ---
        total_truths = _count(db, PlaceTruth)

        # --- Orphaned claims (no matching place) ---
        orphaned_claims_stmt = (
            select(func.count())
            .select_from(PlaceClaim)
            .outerjoin(Place, PlaceClaim.place_id == Place.id)
            .where(Place.id.is_(None))
        )
        orphaned_claims = db.execute(orphaned_claims_stmt).scalar_one()

        report = {
            "places": {
                "total": total_places,
                "active": active_places,
                "inactive": inactive_places,
                "with_menu": places_with_menu,
                "missing_geo": places_no_geo,
                "missing_name": places_no_name,
                "missing_score": places_no_score,
            },
            "claims": {
                "total": total_claims,
                "orphaned": orphaned_claims,
            },
            "truths": {
                "total": total_truths,
            },
        }

        # --- Print report ---
        print("\n" + "=" * 60)
        print("  CRAVE BACKEND DATA VALIDATION REPORT")
        print("=" * 60)

        print("\n[PLACES]")
        print(f"  total          : {total_places}")
        print(f"  active         : {active_places}")
        print(f"  inactive       : {inactive_places}")
        print(f"  with_menu      : {places_with_menu}")
        print(f"  missing_geo    : {places_no_geo}")
        print(f"  missing_name   : {places_no_name}")
        print(f"  missing_score  : {places_no_score}")

        print("\n[CLAIMS]")
        print(f"  total          : {total_claims}")
        print(f"  orphaned       : {orphaned_claims}")

        print("\n[TRUTHS]")
        print(f"  total          : {total_truths}")

        # --- Warnings ---
        warnings = []
        if places_no_geo > 0:
            warnings.append(f"  WARN: {places_no_geo} active places missing geo coords")
        if places_no_name > 0:
            warnings.append(f"  WARN: {places_no_name} places missing name")
        if places_no_score > 0:
            warnings.append(f"  WARN: {places_no_score} active places not scored")
        if orphaned_claims > 0:
            warnings.append(f"  WARN: {orphaned_claims} orphaned claims (no matching place)")

        if warnings:
            print("\n[WARNINGS]")
            for w in warnings:
                print(w)
        else:
            print("\n[OK] No data quality issues found.")

        print("\n" + "=" * 60 + "\n")
        return report

    finally:
        db.close()


if __name__ == "__main__":
    run()
    sys.exit(0)
