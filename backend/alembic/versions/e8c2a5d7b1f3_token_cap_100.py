"""raise the token stock cap to 100

Revision ID: e8c2a5d7b1f3
Revises: d6b1f4a9c8e2
Create Date: 2026-09-08 12:20:00.000000

A productive day releases around 70 tokens, so a cap of 50 threw most of it
away. 100 lets a good day land whole and about a day and a half be banked.
Profiles still on the old default are moved up.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e8c2a5d7b1f3"
down_revision: Union[str, None] = "d6b1f4a9c8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE user_state SET max_tokens = 100 WHERE max_tokens = 50")


def downgrade() -> None:
    op.execute("UPDATE user_state SET max_tokens = 50 WHERE max_tokens = 100")
