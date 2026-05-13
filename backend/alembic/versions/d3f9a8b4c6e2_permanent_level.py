"""permanent level (physical leaves)

Revision ID: d3f9a8b4c6e2
Revises: c8d2e5f7a3b1
Create Date: 2026-05-12 18:00:00.000000

Adds permanent_level to user_leaf_scores and max_level to attr_nodes.
Backfills max_level=10 for the 16 physical leaves.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3f9a8b4c6e2"
down_revision: Union[str, None] = "c8d2e5f7a3b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PHYSICAL_LEAVES = (
    "biceps", "triceps", "deltoide", "antebraco",
    "peitoral", "dorsal", "core", "lombar",
    "quadriceps", "posterior_coxa", "gluteo", "panturrilha",
    "aerobico", "anaerobico",
    "flexibilidade", "estabilidade",
)


def upgrade() -> None:
    op.add_column("attr_nodes", sa.Column("max_level", sa.Integer(), nullable=True))
    op.add_column("user_leaf_scores", sa.Column("permanent_level", sa.Integer(), nullable=False, server_default="0"))

    keys_csv = ",".join(f"'{k}'" for k in PHYSICAL_LEAVES)
    op.execute(f"UPDATE attr_nodes SET max_level = 10 WHERE `key` IN ({keys_csv})")


def downgrade() -> None:
    op.drop_column("user_leaf_scores", "permanent_level")
    op.drop_column("attr_nodes", "max_level")
