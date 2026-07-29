"""add embed fields to crave_items

The share pipeline (share_parser_worker.py) only ever extracted a plain-text
title via oEmbed and discarded everything else TikTok/YouTube's oEmbed
response actually gives us: thumbnail_url, embed html, and the creator's
display name. Without those stored, there was no way for the app to show
"seen on TikTok" content on a place — only a bare matched/unmatched status.

Adds three nullable columns to crave_items:
  - thumbnail_url: the oEmbed thumbnail_url, used for a preview image
  - embed_html: the oEmbed html blob (kept for a future inline-player pass;
    not rendered yet — see place/[id].tsx, which currently just links out
    to the original URL via a thumbnail tap)
  - author_name: the oEmbed author_name (creator handle), for attribution

Revision ID: n1o2p3q4r5s6
Revises: m1n2o3p4q5r6
Create Date: 2026-07-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "n1o2p3q4r5s6"
down_revision = "m1n2o3p4q5r6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crave_items") as batch_op:
        batch_op.add_column(sa.Column("thumbnail_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("embed_html", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("author_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("crave_items") as batch_op:
        batch_op.drop_column("author_name")
        batch_op.drop_column("embed_html")
        batch_op.drop_column("thumbnail_url")
