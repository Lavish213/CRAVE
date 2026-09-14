"""add data source governance audit fields

Revision ID: e3f4g5h6i7j8
Revises: e2f3a4b5c6d7
Create Date: 2026-09-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e3f4g5h6i7j8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "menu_sources" in inspector.get_table_names():
        with op.batch_alter_table("menu_sources") as batch_op:
            if not _has_column(inspector, "menu_sources", "last_failure_at"):
                batch_op.add_column(sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "menu_sources", "last_failure_reason"):
                batch_op.add_column(sa.Column("last_failure_reason", sa.String(128), nullable=True))

    if "menu_submissions" in inspector.get_table_names():
        with op.batch_alter_table("menu_submissions") as batch_op:
            if not _has_column(inspector, "menu_submissions", "evidence_url"):
                batch_op.add_column(sa.Column("evidence_url", sa.String(1024), nullable=True))
            if not _has_column(inspector, "menu_submissions", "evidence_image_id"):
                batch_op.add_column(sa.Column("evidence_image_id", sa.String(36), nullable=True))
            if not _has_column(inspector, "menu_submissions", "evidence_note"):
                batch_op.add_column(sa.Column("evidence_note", sa.String(500), nullable=True))

    if "place_images" in inspector.get_table_names():
        with op.batch_alter_table("place_images") as batch_op:
            if not _has_column(inspector, "place_images", "source_provider"):
                batch_op.add_column(sa.Column("source_provider", sa.String(64), nullable=True))
            if not _has_column(inspector, "place_images", "source_context"):
                batch_op.add_column(sa.Column("source_context", sa.String(64), nullable=True))
            if not _has_column(inspector, "place_images", "source_metadata"):
                batch_op.add_column(sa.Column("source_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "place_images" in inspector.get_table_names():
        with op.batch_alter_table("place_images") as batch_op:
            if _has_column(inspector, "place_images", "source_metadata"):
                batch_op.drop_column("source_metadata")
            if _has_column(inspector, "place_images", "source_context"):
                batch_op.drop_column("source_context")
            if _has_column(inspector, "place_images", "source_provider"):
                batch_op.drop_column("source_provider")

    if "menu_submissions" in inspector.get_table_names():
        with op.batch_alter_table("menu_submissions") as batch_op:
            if _has_column(inspector, "menu_submissions", "evidence_note"):
                batch_op.drop_column("evidence_note")
            if _has_column(inspector, "menu_submissions", "evidence_image_id"):
                batch_op.drop_column("evidence_image_id")
            if _has_column(inspector, "menu_submissions", "evidence_url"):
                batch_op.drop_column("evidence_url")

    if "menu_sources" in inspector.get_table_names():
        with op.batch_alter_table("menu_sources") as batch_op:
            if _has_column(inspector, "menu_sources", "last_failure_reason"):
                batch_op.drop_column("last_failure_reason")
            if _has_column(inspector, "menu_sources", "last_failure_at"):
                batch_op.drop_column("last_failure_at")
