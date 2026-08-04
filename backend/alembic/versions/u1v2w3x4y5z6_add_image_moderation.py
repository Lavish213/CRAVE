"""add image moderation columns and image_reports table

User uploads previously went straight to status="ready" and were
immediately eligible to become a place's primary image, with no safety
check, no quality floor, and is_approved hardcoded True at upload with
nothing anywhere ever setting it False. There was no takedown path.

Adds the moderation state each upload is screened into (see
app/services/images/upload_moderation.py) and the user-report table that
backs reactive moderation.

Existing rows default to "approved": scraped/legacy images never went
through the user-upload path, and retroactively hiding the entire catalog
behind a review queue would empty the app.

Revision ID: u1v2w3x4y5z6
Revises: t1u2v3w4x5y6
Create Date: 2026-08-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "u1v2w3x4y5z6"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("place_images", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "moderation_status",
                sa.String(length=24),
                nullable=False,
                server_default="approved",
            )
        )
        batch_op.add_column(
            sa.Column("moderation_reason", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("blur_score", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "gps_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")
            )
        )
        batch_op.add_column(
            sa.Column(
                "safety_scanned", sa.Boolean(), nullable=False, server_default=sa.text("0")
            )
        )
        batch_op.add_column(
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("reviewed_by", sa.String(length=128), nullable=True))
        batch_op.create_index(
            "ix_place_images_moderation_status", ["moderation_status"], unique=False
        )

    op.create_table(
        "image_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("image_id", sa.String(length=36), nullable=False),
        sa.Column("reporter_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["image_id"], ["place_images.id"],
            name=op.f("fk_image_reports_image_id_place_images"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_reports")),
        sa.UniqueConstraint(
            "image_id", "reporter_id", name="uq_image_reports_image_reporter"
        ),
    )
    with op.batch_alter_table("image_reports", schema=None) as batch_op:
        batch_op.create_index("ix_image_reports_image", ["image_id"], unique=False)
        batch_op.create_index(
            "ix_image_reports_reporter_id", ["reporter_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("image_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_image_reports_reporter_id")
        batch_op.drop_index("ix_image_reports_image")
    op.drop_table("image_reports")

    with op.batch_alter_table("place_images", schema=None) as batch_op:
        batch_op.drop_index("ix_place_images_moderation_status")
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("safety_scanned")
        batch_op.drop_column("gps_verified")
        batch_op.drop_column("blur_score")
        batch_op.drop_column("moderation_reason")
        batch_op.drop_column("moderation_status")
