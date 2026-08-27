"""add decision_role to recommendation_events

Revision ID: b2c3d4e5f6a7
Revises: f8a2c6d90e13
Create Date: 2026-08-27 08:49:13.307209

Backs app/db/models/recommendation_event.py's decision_role -- which of
the Decision Session's three roles (best_fit/safe_bet/wildcard) this
event's card was shown as. Only ever set on surface="decision_session"
rows; every other surface leaves it null. See
docs/decision_session_spec.md.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'f8a2c6d90e13'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("recommendation_events")}

    if "decision_role" not in existing_columns:
        op.add_column(
            "recommendation_events",
            sa.Column("decision_role", sa.String(length=16), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("recommendation_events", "decision_role")
