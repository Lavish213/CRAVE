"""add missing single-column index on place_images.insertion_order

Found via a full-app audit: the model has always declared insertion_order
with index=True, but only the composite (place_id, insertion_order) index
from h1i2j3k4l5m6 was ever actually deployed — the single-column index the
model asked for was never created. alembic autogenerate correctly flagged
this as real drift (not a naming mismatch like everything else that audit
surfaced). CREATE INDEX CONCURRENTLY on Postgres so this doesn't take a
table lock against a live, actively-written table; plain create_index on
SQLite, which has no CONCURRENTLY and no comparable concern.

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
Create Date: 2026-08-05
"""
from __future__ import annotations

from alembic import op


revision = "v1w2x3y4z5a6"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_place_images_insertion_order"
_TABLE = "place_images"
_COLUMNS = ["insertion_order"]


def upgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name == "postgresql":
        # CONCURRENTLY can't run inside the transaction Alembic normally
        # wraps each migration in — autocommit_block() steps outside it.
        with op.get_context().autocommit_block():
            op.create_index(
                _INDEX_NAME,
                _TABLE,
                _COLUMNS,
                unique=False,
                postgresql_concurrently=True,
            )
    else:
        op.create_index(_INDEX_NAME, _TABLE, _COLUMNS, unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(
                _INDEX_NAME,
                table_name=_TABLE,
                postgresql_concurrently=True,
            )
    else:
        op.drop_index(_INDEX_NAME, table_name=_TABLE)
