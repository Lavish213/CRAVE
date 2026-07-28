"""add upload pipeline fields to place_images

app/services/upload/upload_service.py (create_upload_slot) and
app/workers/image_processing_worker.py (process_image_upload) were built
against a PlaceImage shape that never actually existed in the model or the
database: orig_key, processed_key, thumb_key, status, processing_version,
is_approved, phash. Every call to POST /api/v1/upload/request was raising a
TypeError from the SQLAlchemy declarative constructor rejecting unknown
kwargs, before ever touching R2 or the database — this was broken
independent of R2 credentials.

Also makes `url` nullable: user-uploaded images don't have a url until the
background worker finishes processing and derives one from processed_key
(see key_builder.py's "never store full URLs, only keys" comment) — only
legacy Google-Places-scraped rows populate `url` at insert time.

Also adds `uploaded_by` (nullable, indexed) for uploader attribution, which
didn't exist anywhere — there was previously no way to know who uploaded a
given photo.

Revision ID: m1n2o3p4q5r6
Revises: l1m2n3o4p5q6
Create Date: 2026-07-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "m1n2o3p4q5r6"
down_revision = "l1m2n3o4p5q6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("place_images") as batch_op:
        batch_op.alter_column("url", existing_type=sa.String(length=512), nullable=True)

        batch_op.add_column(sa.Column("orig_key", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("processed_key", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("thumb_key", sa.String(length=512), nullable=True))

        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'ready'"),
            )
        )
        batch_op.add_column(sa.Column("processing_version", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_approved",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )
        batch_op.add_column(sa.Column("phash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("uploaded_by", sa.String(length=128), nullable=True))

        batch_op.create_index("ix_place_images_status", ["status"])
        batch_op.create_index("ix_place_images_phash", ["phash"])
        batch_op.create_index("ix_place_images_uploaded_by", ["uploaded_by"])


def downgrade() -> None:
    with op.batch_alter_table("place_images") as batch_op:
        batch_op.drop_index("ix_place_images_uploaded_by")
        batch_op.drop_index("ix_place_images_phash")
        batch_op.drop_index("ix_place_images_status")

        batch_op.drop_column("uploaded_by")
        batch_op.drop_column("error_message")
        batch_op.drop_column("phash")
        batch_op.drop_column("is_approved")
        batch_op.drop_column("processing_version")
        batch_op.drop_column("thumb_key")
        batch_op.drop_column("processed_key")
        batch_op.drop_column("orig_key")

        batch_op.alter_column("url", existing_type=sa.String(length=512), nullable=False)
