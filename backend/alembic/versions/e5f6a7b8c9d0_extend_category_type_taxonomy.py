"""extend category type taxonomy, retire specialty

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-09-01

Corrects E8: `categories.type` already existed (cuisine/venue/specialty)
but was completely unsurfaced end-to-end, and `specialty` itself was a
grab-bag mixing dietary restrictions, ownership/identity attributes, an
external recognition award, and occasion/vibe tags. See
docs/CATEGORY_TAXONOMY_DESIGN_2026-08-31.md for the full reasoning.

Retypes the 11 `specialty` rows into `dietary` / `ownership` / `occasion`
/ `recognition`, then tightens the check constraint to the new 6-value
set. Category identity (`id`, derived from `slug`) never changes, and no
`Place` or `place_categories` row is touched -- this only recategorizes
which type bucket each Category row reports.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_VALUES = ("cuisine", "venue", "specialty")
_NEW_VALUES = ("cuisine", "venue", "dietary", "ownership", "occasion", "recognition")

# (slug, new_type) for every row currently typed `specialty`.
_RETYPES = (
    ("halal", "dietary"),
    ("vegan", "dietary"),
    ("gluten_free", "dietary"),
    ("family_owned", "ownership"),
    ("black_owned", "ownership"),
    ("woman_owned", "ownership"),
    ("local_favorite", "occasion"),
    ("late_night", "occasion"),
    ("romantic", "occasion"),
    ("kid_friendly", "occasion"),
    ("michelin_rated", "recognition"),
    # `other` was filed under specialty despite sitting in the seed
    # file's cuisine section -- a pre-existing inconsistency, not
    # something this migration should perpetuate. It's already treated
    # as a void/generic category everywhere it's read (see
    # _VOID_CATEGORIES in app/api/v1/schemas/places.py), so its type
    # barely matters functionally; cuisine matches where it's grouped.
    ("other", "cuisine"),
)

_categories = sa.table(
    "categories",
    sa.column("slug", sa.String),
    sa.column("type", sa.String),
)


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        # `type` was VARCHAR(9), sized for "specialty" (9 chars) --
        # "recognition" is 11. Widen before anything writes a longer
        # value into it, or Postgres rejects the UPDATE below outright
        # (confirmed: SQLite doesn't enforce VARCHAR length at all, so
        # this only surfaced against real Postgres in CI, not locally).
        batch_op.alter_column(
            "type",
            existing_type=sa.String(9),
            type_=sa.String(11),
        )
        batch_op.drop_constraint("category_type_enum", type_="check")

    for slug, new_type in _RETYPES:
        op.execute(
            _categories.update()
            .where(_categories.c.slug == slug)
            .values(type=new_type)
        )

    with op.batch_alter_table("categories") as batch_op:
        batch_op.create_check_constraint(
            "category_type_enum",
            sa.column("type").in_(_NEW_VALUES),
        )


def downgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_constraint("category_type_enum", type_="check")

    for slug, _new_type in _RETYPES:
        op.execute(
            _categories.update()
            .where(_categories.c.slug == slug)
            .values(type="specialty")
        )

    with op.batch_alter_table("categories") as batch_op:
        batch_op.create_check_constraint(
            "category_type_enum",
            sa.column("type").in_(_OLD_VALUES),
        )
        # Safe now: every value has already been reverted to <=9 chars
        # above, before the column shrinks back to its original size.
        batch_op.alter_column(
            "type",
            existing_type=sa.String(11),
            type_=sa.String(9),
        )
