from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.city import City


# --------------------------------------------------
# PATH (CWD SAFE)
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "cities"


# --------------------------------------------------
# Utilities
# --------------------------------------------------

def normalize_slug(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "-")
        .replace(".", "")
    )


# --------------------------------------------------
# Seeder
# --------------------------------------------------

def seed_cities(db: Session) -> None:
    inserted = 0
    updated = 0

    if not DATA_DIR.exists():
        raise RuntimeError(f"City data directory missing: {DATA_DIR}")

    files = sorted(DATA_DIR.glob("*.json"))

    if not files:
        raise RuntimeError(f"No city files found in: {DATA_DIR}")

    # 🔥 preload all cities (CRITICAL FIX)
    existing_cities = {
        c.slug: c for c in db.query(City).all()
    }

    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))

        if not isinstance(payload, list):
            raise RuntimeError(f"Invalid JSON format in {file.name}")

        print(f"\n🌎 Processing region file: {file.name}")

        for row in payload:

            required_fields = {"name", "state", "country", "lat", "lng"}
            missing = required_fields - row.keys()

            if missing:
                raise RuntimeError(
                    f"{file.name} missing required fields: {missing}"
                )

            name = row["name"]
            slug = normalize_slug(name)

            existing = existing_cities.get(slug)

            if existing:
                changed = False

                if existing.state != row["state"]:
                    existing.state = row["state"]
                    changed = True

                if existing.country != row["country"]:
                    existing.country = row["country"]
                    changed = True

                if existing.lat != row["lat"]:
                    existing.lat = row["lat"]
                    changed = True

                if existing.lng != row["lng"]:
                    existing.lng = row["lng"]
                    changed = True

                if changed:
                    updated += 1
                    print(f"♻️ Updated: {name}")

                continue

            city = City(
                name=name,
                slug=slug,
                state=row["state"],
                country=row["country"],
                lat=row["lat"],
                lng=row["lng"],
                is_active=True,
            )

            db.add(city)
            existing_cities[slug] = city  # 🔥 keep map in sync
            inserted += 1
            print(f"✅ Inserted: {name}")

    db.commit()

    print("\n---")
    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")
    print(f"Total Cities: {len(existing_cities)}")
    print("---\n")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

def main() -> None:
    db = SessionLocal()
    try:
        seed_cities(db)
    except Exception as e:
        db.rollback()
        print("❌ city seed failed:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()