"""add place_reports table

Revision ID: b3f09f202a2f
Revises: f6a7b8c9d0e1
Create Date: 2026-09-02

Backs app/db/models/place_report.py -- reactive moderation for the
place itself (wrong hours, closed, duplicate, wrong menu, wrong info),
mirroring ImageReport/VideoReport's report + review-queue pattern (see
app/api/v1/routes/moderation.py). Unlike those, there's no auto-hide
column here -- resolution is human-only via resolved_at/resolved_by,
never automatic on report volume.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b3f09f202a2f"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "place_reports" in set(inspector.get_table_names()):
        return

    op.create_table(
        "place_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("place_id", sa.String(length=36), nullable=False),
        sa.Column("reporter_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"],
            name=op.f("fk_place_reports_place_id_places"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_reports")),
        sa.UniqueConstraint(
            "place_id", "reporter_id", name="uq_place_reports_place_reporter"
        ),
    )
    op.create_index("ix_place_reports_place", "place_reports", ["place_id"])
    op.create_index(
        "ix_place_reports_reporter_id", "place_reports", ["reporter_id"]
    )


def downgrade() -> None:
    op.drop_table("place_reports")
