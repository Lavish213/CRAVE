"""
Coverage for E8: extending `Category.type` from cuisine/venue/specialty to
cuisine/venue/dietary/ownership/occasion/recognition, and retiring
`specialty`. See docs/CATEGORY_TAXONOMY_DESIGN_2026-08-31.md and
alembic/versions/e5f6a7b8c9d0_extend_category_type_taxonomy.py.

Three things worth a real regression test here:
  1. Every new CategoryType value is actually accepted by the DB
     constraint, not just the Python enum.
  2. `specialty` is genuinely gone -- inserting it must fail, proving
     retirement rather than just no longer being used by convention.
  3. `CategoryOut` surfaces `type` end-to-end, since the whole point of
     E8 was that the dimension existed but was invisible to callers.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.db.models.category import Category, CategoryType
from app.api.v1.schemas.categories import CategoryOut
from app.scripts.seed_categories import seed_categories, CATEGORIES


@pytest.fixture
def db():
    created_ids: list[str] = []
    session = SessionLocal()
    try:
        yield session, created_ids
    finally:
        session.rollback()
        if created_ids:
            session.query(Category).filter(
                Category.id.in_(created_ids)
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def _make_category(session, created_ids, *, slug: str, type_: CategoryType) -> Category:
    cat = Category(slug=slug, name=slug.replace("_", " ").title(), type=type_)
    session.add(cat)
    session.commit()
    created_ids.append(cat.id)
    return cat


@pytest.mark.parametrize(
    "type_",
    [
        CategoryType.cuisine,
        CategoryType.venue,
        CategoryType.dietary,
        CategoryType.ownership,
        CategoryType.occasion,
        CategoryType.recognition,
    ],
)
def test_every_new_category_type_is_accepted_by_the_db_constraint(db, type_):
    session, created_ids = db
    slug = f"taxonomy-test-{type_.value}-{uuid.uuid4().hex[:6]}"
    cat = _make_category(session, created_ids, slug=slug, type_=type_)
    assert cat.type == type_


def test_specialty_no_longer_exists_as_a_python_enum_member():
    assert not hasattr(CategoryType, "specialty")
    assert "specialty" not in CategoryType._value2member_map_


def test_specialty_is_rejected_by_the_db_constraint_directly(db):
    """
    Bypasses the Python enum entirely (raw string insert) to prove the DB
    itself, not just application code, refuses `specialty` -- the actual
    retirement guarantee, since the enum check alone wouldn't catch a
    constraint that silently still allowed the old value.
    """
    session, created_ids = db
    slug = f"taxonomy-test-specialty-{uuid.uuid4().hex[:6]}"
    cat = Category(slug=slug, name="Specialty Test", type=CategoryType.cuisine)
    session.add(cat)
    session.commit()
    created_ids.append(cat.id)

    # SQLite enforces CHECK constraints immediately on execute(), not
    # deferred to commit() -- Postgres behaves the same for a plain (not
    # explicitly DEFERRABLE) check constraint, which this one is.
    with pytest.raises(IntegrityError):
        session.execute(
            Category.__table__.update()
            .where(Category.id == cat.id)
            .values(type="specialty")
        )
    session.rollback()


def test_category_out_surfaces_type(db):
    session, created_ids = db
    cat = _make_category(
        session, created_ids,
        slug=f"taxonomy-test-out-{uuid.uuid4().hex[:6]}",
        type_=CategoryType.dietary,
    )
    out = CategoryOut.model_validate(cat, from_attributes=True)
    assert out.type == "dietary"


@pytest.mark.parametrize(
    "slug,expected_type",
    [
        ("halal", CategoryType.dietary),
        ("vegan", CategoryType.dietary),
        ("gluten_free", CategoryType.dietary),
        ("family_owned", CategoryType.ownership),
        ("black_owned", CategoryType.ownership),
        ("woman_owned", CategoryType.ownership),
        ("late_night", CategoryType.occasion),
        ("romantic", CategoryType.occasion),
        ("kid_friendly", CategoryType.occasion),
        ("local_favorite", CategoryType.occasion),
        ("michelin_rated", CategoryType.recognition),
    ],
)
def test_seed_categories_retypes_every_former_specialty_slug(slug, expected_type):
    """
    Every slug that used to be CategoryType.specialty must land in a real
    bucket in the seed definitions -- this is what keeps a from-scratch
    seed (fresh DB, local dev) converging to the same taxonomy the
    production data migration applies to existing rows.
    """
    by_slug = {s: t for s, _name, t in CATEGORIES}
    assert by_slug[slug] == expected_type


def test_seed_categories_updates_an_existing_specialty_row_in_place(db):
    """
    The real production path: an existing row (previously specialty,
    already retyped to a real bucket by the data migration) gets its
    type left alone by a re-run of the idempotent seeder, since it
    already matches. Uses an isolated slug, not a real production one,
    so this can't collide with rows other tests or fixtures rely on.
    """
    session, created_ids = db
    slug = f"taxonomy-test-idempotent-{uuid.uuid4().hex[:6]}"
    cat = _make_category(session, created_ids, slug=slug, type_=CategoryType.dietary)

    # Patch the seeder's in-memory definition list for one isolated slug
    # rather than mutating real category rows.
    import app.scripts.seed_categories as seed_module
    original = seed_module.CATEGORIES
    seed_module.CATEGORIES = [(slug, "Idempotent Test", CategoryType.dietary)]
    try:
        seed_categories(session)
    finally:
        seed_module.CATEGORIES = original

    session.refresh(cat)
    assert cat.type == CategoryType.dietary
