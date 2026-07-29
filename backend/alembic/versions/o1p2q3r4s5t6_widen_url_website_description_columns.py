"""widen place_images.url, discovery_candidates.website, menu_items.description

Real scraped data (Google Places photo URLs, DoorDash affiliate URLs with
long query strings, full menu-item descriptions) routinely exceeds the
widths these columns were originally given, which aborted a data restore
from the local crave_staging database: COPY failed outright on the first
oversized row for each of these three tables.

migrate_sqlite_to_pg.py already independently discovered this exact problem
and widened these same three columns ad hoc before its own restore — this
migration makes that fix a permanent part of the schema instead.

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-07-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "o1p2q3r4s5t6"
down_revision = "n1o2p3q4r5s6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "place_images", "url",
        existing_type=sa.String(length=512),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )
    op.alter_column(
        "discovery_candidates", "website",
        existing_type=sa.String(length=255),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    op.alter_column(
        "menu_items", "description",
        existing_type=sa.String(length=1000),
        type_=sa.String(length=2000),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "menu_items", "description",
        existing_type=sa.String(length=2000),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )
    op.alter_column(
        "discovery_candidates", "website",
        existing_type=sa.String(length=512),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "place_images", "url",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
