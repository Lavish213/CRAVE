"""add menu_submissions table

Revision ID: x1y2z3a4b5c6
Revises: w1x2y3z4a5b6
Create Date: 2026-08-09

Backs app/db/models/menu_submission.py — the restaurant-owner / user menu
self-submission feature. Submissions are staged here for moderation and are
never read directly by /places/{id}/menu; on approval each item is written
as a PlaceClaim and run through the existing materialize_menu_truth ->
MenuPublisher pipeline (see menu_submission.py's docstring).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "x1y2z3a4b5c6"
down_revision = "w1x2y3z4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "menu_submissions" in inspector.get_table_names():
        return

    op.create_table(
        "menu_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "place_id",
            sa.String(36),
            sa.ForeignKey("places.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("submitted_by", sa.String(255), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index(
        "ix_menu_submissions_place_status",
        "menu_submissions",
        ["place_id", "status"],
    )
    op.create_index(
        "ix_menu_submissions_status_created",
        "menu_submissions",
        ["status", "created_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "menu_submissions" not in inspector.get_table_names():
        return

    op.drop_index("ix_menu_submissions_status_created", table_name="menu_submissions")
    op.drop_index("ix_menu_submissions_place_status", table_name="menu_submissions")
    op.drop_table("menu_submissions")
