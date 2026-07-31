"""add corroboration_keys to discovery_candidates

The user-corroboration confidence merge (GPS confirmation, unmatched share,
hitlist suggestion, hitlist save) was a max() over confidence_score, not an
accumulation — so no combination of user-submitted signals could ever cross
MIN_CONFIDENCE_THRESHOLD (0.72) since the highest single one of them
(hitlist save, 0.45) already caps it. See candidate_store_v2.py: a genuinely
new corroborating signal (tracked here by contributor key) now adds to
confidence_score instead of just taking the max, so multiple independent
people confirming the same spot can actually promote it, matching the
feature's own documented intent.

Revision ID: p1q2r3s4t5u6
Revises: o1p2q3r4s5t6
Create Date: 2026-07-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "p1q2r3s4t5u6"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discovery_candidates",
        sa.Column("corroboration_keys", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovery_candidates", "corroboration_keys")
