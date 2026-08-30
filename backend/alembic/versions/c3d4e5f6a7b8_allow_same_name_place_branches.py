"""allow distinct same-name place branches in one city

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-29
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Name is presentation data, not identity. Chains commonly have multiple
    # locations inside one city; entity resolution already uses address,
    # website and geo proximity to decide whether two records are the same.
    with op.batch_alter_table("places") as batch_op:
        batch_op.drop_constraint("uq_places_city_name", type_="unique")


def downgrade() -> None:
    # Safe for the pre-upgrade dataset. A downgrade after adding legitimate
    # same-name branches will fail rather than silently deleting/merging data.
    with op.batch_alter_table("places") as batch_op:
        batch_op.create_unique_constraint(
            "uq_places_city_name",
            ["city_id", "name"],
        )
