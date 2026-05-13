"""programming actions contributions

Revision ID: e5a1c9d8b2f4
Revises: d3f9a8b4c6e2
Create Date: 2026-05-12 19:00:00.000000

Inserts contributions for the 10 programming actions from attributes_tree.json.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "e5a1c9d8b2f4"
down_revision: Union[str, None] = "d3f9a8b4c6e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_ACTIONS = (
    "BUG FIX", "BUG FIX (AI)",
    "FEATURE", "FEATURE (AI)",
    "REFACTOR", "REFACTOR (AI)",
    "CODE REVIEW", "WRITE TESTS",
    "WRITE DOCS", "ARCHITECTURE",
)


def upgrade() -> None:
    seed_path = Path(__file__).resolve().parents[2] / "data" / "attributes_tree.json"
    with seed_path.open("r", encoding="utf-8") as f:
        seed = json.load(f)

    conn = op.get_bind()
    leaf_rows = conn.execute(sa.text("SELECT id, `key` FROM attr_nodes WHERE is_leaf=1")).fetchall()
    leaf_id = {r[1]: r[0] for r in leaf_rows}

    contribs_tbl = sa.table(
        "action_contributions",
        sa.column("action_name", sa.String),
        sa.column("leaf_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )
    rows = [
        {
            "action_name": c["action"].upper(),
            "leaf_id": leaf_id[c["leaf"]],
            "weight": float(c["weight"]),
        }
        for c in seed["contributions"]
        if c["action"] in NEW_ACTIONS
    ]
    if rows:
        op.bulk_insert(contribs_tbl, rows)


def downgrade() -> None:
    keys = ",".join(f"'{a}'" for a in NEW_ACTIONS)
    op.execute(f"DELETE FROM action_contributions WHERE action_name IN ({keys})")
