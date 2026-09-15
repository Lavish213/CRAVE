"""add craves data model

Revision ID: h9i0j1k2l3m4
Revises: f4g5h6i7j8k9
Create Date: 2026-09-14

Adds the product-facing Craves contract that frontend P0.6 needs:
collections, tags, per-place want-to-try/tried state, notes, and favorite
dishes. This deliberately does not replace crave_items, which remains the
share/import pipeline table.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.db.models.base import JSONType


revision = "h9i0j1k2l3m4"
down_revision = "f4g5h6i7j8k9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crave_collections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crave_collections")),
        sa.UniqueConstraint("user_id", "name", name="uq_crave_collections_user_name"),
    )
    with op.batch_alter_table("crave_collections") as batch_op:
        batch_op.create_index("ix_crave_collections_user_id", ["user_id"], unique=False)
        batch_op.create_index(
            "ix_crave_collections_user_sort",
            ["user_id", "sort_order", "created_at"],
            unique=False,
        )

    op.create_table(
        "crave_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("color", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crave_tags")),
        sa.UniqueConstraint("user_id", "name", name="uq_crave_tags_user_name"),
    )
    with op.batch_alter_table("crave_tags") as batch_op:
        batch_op.create_index("ix_crave_tags_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_crave_tags_user_created", ["user_id", "created_at"], unique=False)

    op.create_table(
        "crave_place_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("place_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="want_to_try",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("favorite_dishes", JSONType, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('want_to_try', 'tried')", name="ck_crave_place_states_status"),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["places.id"],
            name=op.f("fk_crave_place_states_place_id_places"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crave_place_states")),
        sa.UniqueConstraint("user_id", "place_id", name="uq_crave_place_states_user_place"),
    )
    with op.batch_alter_table("crave_place_states") as batch_op:
        batch_op.create_index("ix_crave_place_states_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_crave_place_states_place_id", ["place_id"], unique=False)
        batch_op.create_index(
            "ix_crave_place_states_user_status",
            ["user_id", "status", "updated_at"],
            unique=False,
        )

    op.create_table(
        "crave_collection_places",
        sa.Column("collection_id", sa.String(length=36), nullable=False),
        sa.Column("state_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["crave_collections.id"],
            name=op.f("fk_crave_collection_places_collection_id_crave_collections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["state_id"],
            ["crave_place_states.id"],
            name=op.f("fk_crave_collection_places_state_id_crave_place_states"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("collection_id", "state_id", name=op.f("pk_crave_collection_places")),
    )
    with op.batch_alter_table("crave_collection_places") as batch_op:
        batch_op.create_index("ix_crave_collection_places_state", ["state_id"], unique=False)

    op.create_table(
        "crave_place_tags",
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.Column("state_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["crave_tags.id"],
            name=op.f("fk_crave_place_tags_tag_id_crave_tags"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["state_id"],
            ["crave_place_states.id"],
            name=op.f("fk_crave_place_tags_state_id_crave_place_states"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tag_id", "state_id", name=op.f("pk_crave_place_tags")),
    )
    with op.batch_alter_table("crave_place_tags") as batch_op:
        batch_op.create_index("ix_crave_place_tags_state", ["state_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("crave_place_tags") as batch_op:
        batch_op.drop_index("ix_crave_place_tags_state")
    op.drop_table("crave_place_tags")

    with op.batch_alter_table("crave_collection_places") as batch_op:
        batch_op.drop_index("ix_crave_collection_places_state")
    op.drop_table("crave_collection_places")

    with op.batch_alter_table("crave_place_states") as batch_op:
        batch_op.drop_index("ix_crave_place_states_user_status")
        batch_op.drop_index("ix_crave_place_states_place_id")
        batch_op.drop_index("ix_crave_place_states_user_id")
    op.drop_table("crave_place_states")

    with op.batch_alter_table("crave_tags") as batch_op:
        batch_op.drop_index("ix_crave_tags_user_created")
        batch_op.drop_index("ix_crave_tags_user_id")
    op.drop_table("crave_tags")

    with op.batch_alter_table("crave_collections") as batch_op:
        batch_op.drop_index("ix_crave_collections_user_sort")
        batch_op.drop_index("ix_crave_collections_user_id")
    op.drop_table("crave_collections")
