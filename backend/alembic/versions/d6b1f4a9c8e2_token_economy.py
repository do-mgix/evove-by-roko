"""token economy: earned by productivity, spent on leisure

Revision ID: d6b1f4a9c8e2
Revises: c4a8e2f6b9d3
Create Date: 2026-09-08 11:40:00.000000

Tokens used to refill 20/day up to a cap. They are now released by executing
productivity actions and spent by leisure ones, flat per execution. Adds
`token_gain` to the catalog and to the user's own actions, reseeds both token
columns from attributes_tree.json, and drops the refill bookkeeping.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "d6b1f4a9c8e2"
down_revision: Union[str, None] = "c4a8e2f6b9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("action_templates", sa.Column("token_gain", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("actions", sa.Column("token_gain", sa.Integer(), nullable=False, server_default="0"))

    seed_path = Path(__file__).resolve().parents[1] / "seeds" / "attributes_tree.pre_engine.json"
    with seed_path.open("r", encoding="utf-8") as f:
        seed = json.load(f)

    # token_cost was rescaled alongside the new gains, so reseed both columns.
    conn = op.get_bind()
    for tpl in seed.get("action_templates", []):
        conn.execute(
            sa.text(
                "UPDATE action_templates SET token_cost = :c, token_gain = :g "
                "WHERE action_name = :n"
            ),
            {"c": int(tpl.get("token_cost", 0)), "g": int(tpl.get("token_gain", 0)),
             "n": tpl["action"].upper()},
        )

    # Keep already-owned actions in step with the catalog.
    op.execute(
        """
        UPDATE actions a
        JOIN action_templates t ON t.action_name = a.name
        SET a.token_cost = t.token_cost, a.token_gain = t.token_gain
        """
    )

    op.drop_column("user_state", "daily_refill")
    op.drop_column("user_state", "last_token_refill")


def downgrade() -> None:
    op.add_column("user_state", sa.Column("last_token_refill", sa.Date(), nullable=True))
    op.add_column("user_state", sa.Column("daily_refill", sa.Integer(), nullable=False, server_default="20"))
    op.drop_column("actions", "token_gain")
    op.drop_column("action_templates", "token_gain")
