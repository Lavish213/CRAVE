"""add grubhub_url and menu_source_url to places

Revision ID: a3f1b2c4d5e6
Revises: 1c24b5d58ddf
Create Date: 2026-04-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'a3f1b2c4d5e6'
down_revision = '1c24b5d58ddf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("places") as batch_op:
        batch_op.add_column(sa.Column("grubhub_url", sa.String(1024), nullable=True))
        batch_op.add_column(sa.Column("menu_source_url", sa.String(1024), nullable=True))
        batch_op.create_index("ix_places_grubhub_url", ["grubhub_url"])


def downgrade() -> None:
    with op.batch_alter_table("places") as batch_op:
        batch_op.drop_index("ix_places_grubhub_url")
        batch_op.drop_column("grubhub_url")
        batch_op.drop_column("menu_source_url")
