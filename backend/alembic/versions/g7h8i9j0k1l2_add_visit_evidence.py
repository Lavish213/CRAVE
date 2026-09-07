"""add canonical visit evidence

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-07

Creates the visit-evidence authority required by Rank Home. Existing explicit
"visited" save-memory declarations are backfilled as declared evidence so the
migration preserves user history instead of making the new queue start from
zero for people who already told CRAVE they went somewhere.
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visit_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("place_id", sa.String(length=36), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("factual_history", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("recommendation_influence", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tier in ('declared', 'verified', 'inferred')",
            name="ck_visit_evidence_visit_evidence_valid_tier",
        ),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"],
            name="fk_visit_evidence_place_id_places",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_visit_evidence"),
    )
    op.create_index(
        "ix_visit_evidence_user_tier_occurred",
        "visit_evidence",
        ["user_id", "tier", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_visit_evidence_user_place",
        "visit_evidence",
        ["user_id", "place_id"],
        unique=False,
    )
    op.create_index(
        "ix_visit_evidence_source_ref",
        "visit_evidence",
        ["source", "source_ref"],
        unique=False,
    )

    # Portable Python-side backfill: SQLite has no UUID generator and CI
    # exercises both SQLite and Postgres. Only explicit app-save declarations
    # count here; no location or inferred data is promoted.
    bind = op.get_bind()
    hitlist = sa.table(
        "hitlist_saves",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("place_id", sa.String),
        sa.column("visited", sa.Boolean),
        sa.column("visited_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    evidence = sa.table(
        "visit_evidence",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("place_id", sa.String),
        sa.column("tier", sa.String),
        sa.column("source", sa.String),
        sa.column("source_ref", sa.String),
        sa.column("occurred_at", sa.DateTime(timezone=True)),
        sa.column("confirmed_at", sa.DateTime(timezone=True)),
        sa.column("factual_history", sa.Boolean),
        sa.column("recommendation_influence", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    rows = bind.execute(
        sa.select(
            hitlist.c.id,
            hitlist.c.user_id,
            hitlist.c.place_id,
            hitlist.c.visited_at,
            hitlist.c.created_at,
        ).where(
            hitlist.c.visited.is_(True),
            hitlist.c.place_id.is_not(None),
        )
    ).mappings().all()

    if rows:
        bind.execute(
            evidence.insert(),
            [
                {
                    "id": str(uuid.uuid4()),
                    "user_id": row["user_id"],
                    "place_id": row["place_id"],
                    "tier": "declared",
                    "source": "save_memory",
                    "source_ref": row["id"],
                    "occurred_at": row["visited_at"] or row["created_at"],
                    "confirmed_at": row["visited_at"] or row["created_at"],
                    "factual_history": True,
                    "recommendation_influence": True,
                    "created_at": row["visited_at"] or row["created_at"],
                    "updated_at": row["visited_at"] or row["created_at"],
                }
                for row in rows
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_visit_evidence_source_ref", table_name="visit_evidence")
    op.drop_index("ix_visit_evidence_user_place", table_name="visit_evidence")
    op.drop_index("ix_visit_evidence_user_tier_occurred", table_name="visit_evidence")
    op.drop_table("visit_evidence")
