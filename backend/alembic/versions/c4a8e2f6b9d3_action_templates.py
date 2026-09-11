"""action templates (unit, difficulty and prices)

Revision ID: c4a8e2f6b9d3
Revises: b2e7d9c4a6f1
Create Date: 2026-09-08 10:20:00.000000

Until now load_packages() handed every catalog action the same hardcoded
`type=0, diff=1, cost=0, token_cost=0`. This table carries the real metadata,
seeded from the `action_templates` block of attributes_tree.json, and the
existing user actions are backfilled from it so bought rows and the catalog
agree.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "c4a8e2f6b9d3"
down_revision: Union[str, None] = "b2e7d9c4a6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "action_templates",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("action_name", sa.String(128), nullable=False, unique=True),
        sa.Column("type", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("diff", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_cost", sa.Integer(), nullable=False, server_default="0"),
    )

    seed_path = Path(__file__).resolve().parents[1] / "seeds" / "attributes_tree.pre_engine.json"
    with seed_path.open("r", encoding="utf-8") as f:
        seed = json.load(f)

    templates_tbl = sa.table(
        "action_templates",
        sa.column("action_name", sa.String),
        sa.column("type", sa.Integer),
        sa.column("diff", sa.Integer),
        sa.column("cost", sa.Integer),
        sa.column("token_cost", sa.Integer),
    )
    rows = [
        {
            "action_name": t["action"].upper(),
            "type": int(t.get("type", 0)),
            "diff": int(t.get("diff", 1)),
            "cost": int(t.get("cost", 0)),
            "token_cost": int(t.get("token_cost", 0)),
        }
        for t in seed.get("action_templates", [])
    ]
    if rows:
        op.bulk_insert(templates_tbl, rows)

    # Actions bought before this migration all carry type=0/diff=1/token_cost=0.
    # Align them with the catalog so an owned action behaves like its template.
    op.execute(
        """
        UPDATE actions a
        JOIN action_templates t ON t.action_name = a.name
        SET a.type = t.type, a.diff = t.diff, a.token_cost = t.token_cost
        """
    )


def downgrade() -> None:
    # The per-action metadata on `actions` is not restored: the pre-migration
    # values were the same constant for every row.
    op.drop_table("action_templates")
