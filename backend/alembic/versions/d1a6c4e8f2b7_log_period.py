"""logs: the period of the day

Revision ID: d1a6c4e8f2b7
Revises: c3f8a1d6e9b4
Create Date: 2026-10-01 10:30:00.000000

The plain-text journal files every line under mo, ev or ni. A log now carries
the same, chosen when acting so a ride logged at night can still be the
morning's. Existing logs take the period of their timestamp.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1a6c4e8f2b7"
down_revision: Union[str, None] = "c3f8a1d6e9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("logs", sa.Column("period", sa.String(2), nullable=True))
    op.execute("""UPDATE logs SET period = CASE
        WHEN HOUR(timestamp) >= 5 AND HOUR(timestamp) < 12 THEN 'mo'
        WHEN HOUR(timestamp) >= 12 AND HOUR(timestamp) < 18 THEN 'ev'
        ELSE 'ni' END""")


def downgrade() -> None:
    op.drop_column("logs", "period")
