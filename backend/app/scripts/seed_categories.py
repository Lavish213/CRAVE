from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.category import Category, CategoryType


# ------------------------------------------------------------
# CATEGORY DEFINITIONS (LOCKED ORDER)
# ------------------------------------------------------------

CATEGORIES: list[tuple[str, str, CategoryType]] = [

    # ---------------- CUISINE ----------------
    ("mexican", "Mexican", CategoryType.cuisine),
    ("italian", "Italian", CategoryType.cuisine),
    ("chinese", "Chinese", CategoryType.cuisine),
    ("japanese", "Japanese", CategoryType.cuisine),
    ("korean", "Korean", CategoryType.cuisine),
    ("thai", "Thai", CategoryType.cuisine),
    ("indian", "Indian", CategoryType.cuisine),
    ("mediterranean", "Mediterranean", CategoryType.cuisine),
    ("american", "American", CategoryType.cuisine),
    ("bbq", "BBQ", CategoryType.cuisine),
    ("seafood", "Seafood", CategoryType.cuisine),
    ("pizza", "Pizza", CategoryType.cuisine),
    ("breakfast", "Breakfast", CategoryType.cuisine),
    ("coffee", "Coffee", CategoryType.cuisine),
    ("desserts", "Desserts", CategoryType.cuisine),
    ("other", "Other", CategoryType.cuisine),

    # ---------------- VENUE ----------------
    ("restaurant", "Restaurant", CategoryType.venue),
    ("cafe", "Cafe", CategoryType.venue),
    ("bar", "Bar", CategoryType.venue),
    ("fine_dining", "Fine Dining", CategoryType.venue),
    ("fast_casual", "Fast Casual", CategoryType.venue),

    # ---------------- DIETARY ----------------
    ("halal", "Halal", CategoryType.dietary),
    ("vegan", "Vegan", CategoryType.dietary),
    ("gluten_free", "Gluten Free", CategoryType.dietary),

    # ---------------- OWNERSHIP ----------------
    ("family_owned", "Family Owned", CategoryType.ownership),
    ("black_owned", "Black Owned", CategoryType.ownership),
    ("woman_owned", "Woman Owned", CategoryType.ownership),

    # ---------------- OCCASION ----------------
    ("local_favorite", "Local Favorite", CategoryType.occasion),
    ("late_night", "Late Night", CategoryType.occasion),
    ("romantic", "Romantic", CategoryType.occasion),
    ("kid_friendly", "Kid Friendly", CategoryType.occasion),

    # ---------------- RECOGNITION ----------------
    ("michelin_rated", "Michelin Rated", CategoryType.recognition),
]


# ------------------------------------------------------------
# CORE SEEDER
# ------------------------------------------------------------

def seed_categories(db: Session) -> None:
    inserted = 0
    updated = 0

    # Only fetch needed fields (faster + safer)
    existing_categories = {
        c.slug: c for c in db.query(Category).all()
    }

    for raw_slug, name, type_ in CATEGORIES:

        slug = raw_slug.lower().strip()

        existing = existing_categories.get(slug)

        if existing:
            changed = False

            if existing.name != name:
                existing.name = name
                changed = True

            if existing.type != type_:
                existing.type = type_
                changed = True

            if changed:
                updated += 1

        else:
            db.add(
                Category(
                    slug=slug,
                    name=name,
                    type=type_,
                )
            )
            inserted += 1

    db.commit()

    print("\n🌱 Category Seeding Complete")
    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")
    print(f"Total Categories: {len(existing_categories) + inserted}\n")


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------

def main() -> None:
    db = SessionLocal()
    try:
        seed_categories(db)
    except Exception as e:
        db.rollback()
        print("❌ category seed failed:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()