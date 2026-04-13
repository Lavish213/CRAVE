from __future__ import annotations

import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

# 🔥 CRITICAL: LOAD ALL MODELS INTO REGISTRY
import app.db.models  # noqa: F401

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.category import Category
from app.db.models.place import Place

# --------------------------------------------------
# SAFE IMPORTS
# --------------------------------------------------

try:
    from app.scripts.seed_cities import main as seed_cities_main
    from app.scripts.seed_categories import main as seed_categories_main
    from app.scripts.seed_places import main as seed_places_main
except Exception as e:
    print("❌ Failed to import seed modules.")
    print(f"{type(e).__name__}: {e}")
    sys.exit(1)


# --------------------------------------------------
# PATH
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "app.db"


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _banner(msg: str) -> None:
    print("\n" + "=" * 64)
    print(msg)
    print("=" * 64 + "\n")


def _assert_db_ready() -> None:
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        sys.exit(1)

    engine = create_engine(f"sqlite:///{DB_PATH}")
    inspector = inspect(engine)

    tables = set(inspector.get_table_names())
    engine.dispose()

    if not tables:
        print("❌ Database exists but no tables found.")
        sys.exit(1)

    required = {"cities", "categories", "places"}
    missing = required - tables

    if missing:
        print(f"❌ Missing required tables: {missing}")
        sys.exit(1)


def _count_all() -> dict:
    db: Session = SessionLocal()
    try:
        return {
            "cities": db.query(City).count(),
            "categories": db.query(Category).count(),
            "places": db.query(Place).count(),
        }
    finally:
        db.close()


def _print_counts(stage: str) -> None:
    counts = _count_all()
    print(f"\n📊 {stage}")
    for k, v in counts.items():
        print(f"{k}: {v}")
    print("")


# --------------------------------------------------
# ENTRY
# --------------------------------------------------

def main() -> None:
    _banner("SEED ALL (PRODUCTION ORDER)")

    _assert_db_ready()

    before = _count_all()
    _print_counts("BEFORE")

    try:
        # -----------------------------
        _banner("1/3 — SEED CITIES")
        seed_cities_main()
        _print_counts("AFTER CITIES")

        # sanity check
        if _count_all()["cities"] == 0:
            raise RuntimeError("Cities failed to seed")

        # -----------------------------
        _banner("2/3 — SEED CATEGORIES")
        seed_categories_main()
        _print_counts("AFTER CATEGORIES")

        if _count_all()["categories"] == 0:
            raise RuntimeError("Categories failed to seed")

        # -----------------------------
        _banner("3/3 — SEED PLACES")
        seed_places_main()
        _print_counts("AFTER PLACES")

        if _count_all()["places"] == 0:
            raise RuntimeError("Places failed to seed")

        # -----------------------------
        _banner("✅ SEED ALL COMPLETE")

        after = _count_all()

        print("📈 DELTA")
        for k in after:
            print(f"{k}: +{after[k] - before[k]}")

        print("")

    except Exception as e:
        print("\n❌ SEED ALL FAILED")
        print(f"{type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()