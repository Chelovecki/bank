"""add bank state fields to payments

Revision ID: a4f3a4a98720
Revises: 709daf4a9c6a
Create Date: 2026-03-10 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4f3a4a98720"
down_revision: Union[str, Sequence[str], None] = "709daf4a9c6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("bank_status", sa.String(length=50), nullable=True))
    op.add_column(
        "payments",
        sa.Column("bank_checked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("bank_paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "bank_paid_at")
    op.drop_column("payments", "bank_checked_at")
    op.drop_column("payments", "bank_status")
