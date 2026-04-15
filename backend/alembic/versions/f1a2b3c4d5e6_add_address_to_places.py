"""add address to places

Revision ID: f1a2b3c4d5e6
Revises: b7e2f3a1c9d0
Create Date: 2026-04-14

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'b7e2f3a1c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('places', sa.Column('address', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('places', 'address')
