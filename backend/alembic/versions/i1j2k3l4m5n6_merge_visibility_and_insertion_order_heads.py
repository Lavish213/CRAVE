"""merge visibility and insertion_order heads

Merges two independent branches that both add columns to place_images:
  - d1e2f3a4b5c6: adds visibility_status, quality_score, content_type
  - h1i2j3k4l5m6: adds insertion_order

No schema conflicts; this is a bookkeeping-only merge node.

Revision ID: i1j2k3l4m5n6
Revises: d1e2f3a4b5c6, h1i2j3k4l5m6
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "i1j2k3l4m5n6"
down_revision = ("d1e2f3a4b5c6", "h1i2j3k4l5m6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
