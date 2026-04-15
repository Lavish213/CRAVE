"""add_crave_items_table

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'crave_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column(
            'source_type',
            sa.String(length=50),
            server_default='web',
            nullable=False,
        ),
        sa.Column('raw_content', sa.Text(), nullable=True),
        sa.Column('parsed_place_name', sa.String(length=255), nullable=True),
        sa.Column('parsed_city_hint', sa.String(length=100), nullable=True),
        sa.Column('matched_place_id', sa.String(length=36), nullable=True),
        sa.Column('match_confidence', sa.Float(), nullable=True),
        sa.Column(
            'status',
            sa.String(length=20),
            server_default='pending',
            nullable=False,
        ),
        sa.Column('submitted_by', sa.String(length=255), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['matched_place_id'],
            ['places.id'],
            name=op.f('fk_crave_items_matched_place_id_places'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_crave_items')),
    )
    with op.batch_alter_table('crave_items', schema=None) as batch_op:
        batch_op.create_index('ix_crave_items_status', ['status'], unique=False)
        batch_op.create_index('ix_crave_items_created_at', ['created_at'], unique=False)
        batch_op.create_index('ix_crave_items_matched_place_id', ['matched_place_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('crave_items', schema=None) as batch_op:
        batch_op.drop_index('ix_crave_items_matched_place_id')
        batch_op.drop_index('ix_crave_items_created_at')
        batch_op.drop_index('ix_crave_items_status')

    op.drop_table('crave_items')
