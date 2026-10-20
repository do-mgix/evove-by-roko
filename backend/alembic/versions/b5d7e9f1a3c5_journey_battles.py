"""journey: recoveries, battles against bosses, equipment

Revision ID: b5d7e9f1a3c5
Revises: a2f4c6e8b1d3
Create Date: 2026-10-20 10:00:00.000000

The two recoveries keep when they were last taken, for their cooldowns. Every
fight against a boss is a row: `run` counts the journey's restarts, so a boss
beaten before a restart stands again after it. Equipment is bought once with
points and worn one item per slot.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5d7e9f1a3c5"
down_revision: Union[str, None] = "a2f4c6e8b1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_state", sa.Column("recover_small_at", sa.DateTime(), nullable=True))
    op.add_column("user_state", sa.Column("recover_large_at", sa.DateTime(), nullable=True))
    op.add_column("user_state", sa.Column("recover_uses", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "battles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("boss_name", sa.String(32), nullable=False),
        sa.Column("won", sa.Boolean(), nullable=False),
        sa.Column("dealt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("taken", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_hit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fought_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_battles_user_run", "battles", ["user_id", "run", "stage", "slot"])
    op.create_table(
        "user_equipment",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("item_id", sa.String(32), primary_key=True),
        sa.Column("equipped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bought_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_equipment")
    op.drop_index("ix_battles_user_run", table_name="battles")
    op.drop_table("battles")
    op.drop_column("user_state", "recover_uses")
    op.drop_column("user_state", "recover_large_at")
    op.drop_column("user_state", "recover_small_at")
