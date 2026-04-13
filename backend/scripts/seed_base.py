from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.category import Category


def run() -> None:
    """
    Seed foundational base data.

    Safe to run multiple times.
    Idempotent.
    """

    db: Session = SessionLocal()

    try:
        inserted_cities = 0
        inserted_categories = 0

        # ==================================================
        # CITIES
        # ==================================================
        existing_cities = {
            slug for (slug,) in db.query(City.slug).all()
        }

        cities_to_seed = [
            {"name": "Oakland", "slug": "oakland"},
            {"name": "San Francisco", "slug": "san-francisco"},
        ]

        for c in cities_to_seed:
            slug = c["slug"].strip().lower()

            if slug not in existing_cities:
                db.add(
                    City(
                        name=c["name"],
                        slug=slug,
                        is_active=True,  # 🔥 ensure consistency with main seeder
                    )
                )
                inserted_cities += 1

        if inserted_cities:
            print(f"🌆 seeded cities: {inserted_cities}")
        else:
            print("🌆 cities already seeded")

        # ==================================================
        # CATEGORIES
        # ==================================================
        existing_categories = {
            slug for (slug,) in db.query(Category.slug).all()
        }

        categories_to_seed = [
            {"name": "Mexican", "slug": "mexican"},
            {"name": "Italian", "slug": "italian"},
        ]

        for c in categories_to_seed:
            slug = c["slug"].strip().lower()

            if slug not in existing_categories:
                db.add(
                    Category(
                        name=c["name"],
                        slug=slug,
                    )
                )
                inserted_categories += 1

        if inserted_categories:
            print(f"🍽️ seeded categories: {inserted_categories}")
        else:
            print("🍽️ categories already seeded")

        # ==================================================
        # FINAL COMMIT
        # ==================================================
        db.commit()

        print("\n✅ base seed complete")
        print(f"cities inserted: {inserted_cities}")
        print(f"categories inserted: {inserted_categories}\n")

    except Exception as e:
        db.rollback()
        print("❌ seed failed:", e)
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()