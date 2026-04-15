"""add signal_class to place_signals

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'place_signals',
        sa.Column('signal_class', sa.String(20), nullable=True),
    )
    op.create_index(
        'ix_place_signals_signal_class',
        'place_signals',
        ['signal_class'],
    )

def downgrade() -> None:
    op.drop_index('ix_place_signals_signal_class', table_name='place_signals')
    op.drop_column('place_signals', 'signal_class')
