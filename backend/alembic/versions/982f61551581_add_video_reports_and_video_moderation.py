"""add video_reports table and moderation fields to place_videos

Revision ID: 982f61551581
Revises: aa1bb2cc3dd4
Create Date: 2026-08-24

Backs app/db/models/video_report.py and the moderation_status/
moderation_reason/reviewed_at/reviewed_by columns added to
app/db/models/place_video.py -- reactive moderation for video, mirroring
ImageReport/PlaceImage's report + review-queue pattern (see
app/api/v1/routes/moderation.py).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "982f61551581"
down_revision = "aa1bb2cc3dd4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    existing_columns = {
        c["name"] for c in inspector.get_columns("place_videos")
    } if "place_videos" in existing_tables else set()

    if "moderation_status" not in existing_columns:
        op.add_column(
            "place_videos",
            sa.Column(
                "moderation_status",
                sa.String(length=24),
                nullable=False,
                server_default=sa.text("'approved'"),
            ),
        )
        op.add_column(
            "place_videos",
            sa.Column("moderation_reason", sa.String(length=64), nullable=True),
        )
        op.add_column(
            "place_videos",
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            "place_videos",
            sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        )
        op.create_index(
            "ix_place_videos_moderation_status", "place_videos", ["moderation_status"]
        )

    if "video_reports" not in existing_tables:
        op.create_table(
            "video_reports",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("video_id", sa.String(length=36), nullable=False),
            sa.Column("reporter_id", sa.String(length=128), nullable=False),
            sa.Column("reason", sa.String(length=32), nullable=False),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["video_id"], ["place_videos.id"],
                name=op.f("fk_video_reports_video_id_place_videos"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_video_reports")),
            sa.UniqueConstraint(
                "video_id", "reporter_id", name="uq_video_reports_video_reporter"
            ),
        )
        op.create_index("ix_video_reports_video", "video_reports", ["video_id"])
        op.create_index(
            "ix_video_reports_reporter_id", "video_reports", ["reporter_id"]
        )


def downgrade() -> None:
    op.drop_table("video_reports")
    op.drop_index("ix_place_videos_moderation_status", table_name="place_videos")
    op.drop_column("place_videos", "reviewed_by")
    op.drop_column("place_videos", "reviewed_at")
    op.drop_column("place_videos", "moderation_reason")
    op.drop_column("place_videos", "moderation_status")
