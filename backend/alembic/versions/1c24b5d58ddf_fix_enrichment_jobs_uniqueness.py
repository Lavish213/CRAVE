from alembic import op

# revision identifiers
revision = '1c24b5d58ddf'
down_revision = '994c7522912e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop broken unique constraint
    with op.batch_alter_table("enrichment_jobs") as batch_op:
        batch_op.drop_constraint("uq_active_job_per_place_type", type_="unique")

    # Create correct partial unique index (ONLY for active jobs)
    op.execute("""
        CREATE UNIQUE INDEX uq_active_job_per_place_type
        ON enrichment_jobs(place_id, job_type)
        WHERE is_active = 1
    """)


def downgrade() -> None:
    # Remove partial index
    op.execute("DROP INDEX IF EXISTS uq_active_job_per_place_type")

    # Restore old constraint (not recommended, but needed for downgrade)
    with op.batch_alter_table("enrichment_jobs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_active_job_per_place_type",
            ["place_id", "job_type", "is_active"]
        )