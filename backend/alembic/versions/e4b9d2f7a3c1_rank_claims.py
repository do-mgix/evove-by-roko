"""rank claims: a reward for every rank an attribute reaches

Revision ID: e4b9d2f7a3c1
Revises: d1a6c4e8f2b7
Create Date: 2026-10-01 14:00:00.000000

Each row is the highest rank of one attribute whose reward the profile already
took. No row means nothing claimed yet, so ranks reached before this existed
can be claimed too.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4b9d2f7a3c1"
down_revision: Union[str, None] = "d1a6c4e8f2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rank_claims",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("node_key", sa.String(64), primary_key=True),
        sa.Column("claimed_rank", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("rank_claims")
