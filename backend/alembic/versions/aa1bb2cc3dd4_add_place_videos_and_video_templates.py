"""add place_videos and video_templates tables

Revision ID: aa1bb2cc3dd4
Revises: z1a2b3c4d5e6
Create Date: 2026-08-24

Backs app/db/models/place_video.py and app/db/models/video_template.py --
the short-food-video feature (record -> upload -> compress -> food-score
-> feed), ported from a standalone Node.js reference scaffold onto this
app's actual Python/FastAPI/Postgres stack: no Redis/BullMQ, no separate
schema/migration tool -- one Alembic migration like everything else here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "aa1bb2cc3dd4"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


_STARTER_TEMPLATES = [
    {
        "id": "cheese_pull",
        "name": "Cheese Pull",
        "beat_cues": [
            {"t": 0, "cue": "hold plate steady"},
            {"t": 4, "cue": "pull now"},
            {"t": 8, "cue": "hold"},
        ],
        "min_food_area_pct": 40,
        "sort_order": 1,
    },
    {
        "id": "first_cut",
        "name": "First Cut",
        "beat_cues": [
            {"t": 0, "cue": "knife at edge"},
            {"t": 3, "cue": "cut through"},
            {"t": 8, "cue": "reveal inside"},
        ],
        "min_food_area_pct": 40,
        "sort_order": 2,
    },
    {
        "id": "drizzle",
        "name": "Drizzle/Pour",
        "beat_cues": [
            {"t": 0, "cue": "steady shot"},
            {"t": 2, "cue": "start pour"},
            {"t": 9, "cue": "hold plated look"},
        ],
        "min_food_area_pct": 35,
        "sort_order": 3,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "video_templates" not in existing_tables:
        op.create_table(
            "video_templates",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("overlay_asset_url", sa.String(length=512), nullable=True),
            sa.Column("beat_cues", sa.JSON(), nullable=False),
            sa.Column("min_food_area_pct", sa.Integer(), nullable=False, server_default=sa.text("30")),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_video_templates")),
        )

    if "place_videos" not in existing_tables:
        op.create_table(
            "place_videos",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("place_id", sa.String(length=36), nullable=False),
            sa.Column("uploaded_by", sa.String(length=128), nullable=False),
            sa.Column("template_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("orig_key", sa.String(length=512), nullable=True),
            sa.Column("processed_key", sa.String(length=512), nullable=True),
            sa.Column("thumb_key", sa.String(length=512), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("food_score", sa.Float(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("reject_reason", sa.String(length=32), nullable=True),
            sa.Column("error_message", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["place_id"], ["places.id"], name=op.f("fk_place_videos_place_id_places"), ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["template_id"], ["video_templates.id"], name=op.f("fk_place_videos_template_id_video_templates"), ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_place_videos")),
        )
        op.create_index("ix_place_videos_place_status", "place_videos", ["place_id", "status"])
        op.create_index("ix_place_videos_status_created", "place_videos", ["status", "created_at"])
        op.create_index("ix_place_videos_uploaded_by", "place_videos", ["uploaded_by"])
        op.create_index(
            "uq_place_videos_client_id",
            "place_videos",
            ["client_id"],
            unique=True,
            postgresql_where=sa.text("client_id IS NOT NULL"),
            sqlite_where=sa.text("client_id IS NOT NULL"),
        )

    # Seed starter templates -- data, not code; edit/add rows directly
    # later, no migration needed (see video_template.py's docstring).
    # Plain parameterized INSERT (not op.bulk_insert) so the JSON column
    # value is unambiguous across both SQLite (used by this test suite's
    # local fallback) and Postgres (production) -- SQLAlchemy's generic
    # JSON type expects a JSON-serializable Python value bound as text on
    # SQLite, not a driver-native structure.
    now = datetime.now(timezone.utc)
    for row in _STARTER_TEMPLATES:
        existing = bind.execute(
            sa.text("SELECT 1 FROM video_templates WHERE id = :id"), {"id": row["id"]}
        ).first()
        if existing:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO video_templates
                    (id, name, beat_cues, min_food_area_pct, sort_order, created_at, updated_at)
                VALUES
                    (:id, :name, :beat_cues, :min_food_area_pct, :sort_order, :created_at, :updated_at)
                """
            ).bindparams(sa.bindparam("beat_cues", type_=sa.JSON)),
            {
                "id": row["id"],
                "name": row["name"],
                "beat_cues": row["beat_cues"],
                "min_food_area_pct": row["min_food_area_pct"],
                "sort_order": row["sort_order"],
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_table("place_videos")
    op.drop_table("video_templates")
