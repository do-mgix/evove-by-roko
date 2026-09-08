"""record the token delta on each log

Revision ID: f9d3b6e8a2c4
Revises: e8c2a5d7b1f3
Create Date: 2026-09-08 12:50:00.000000

Signed: positive for what an act released (after the cap took its cut),
negative for what it spent. Logs written before this stay at 0.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9d3b6e8a2c4"
down_revision: Union[str, None] = "e8c2a5d7b1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("logs", sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("logs", "tokens")
