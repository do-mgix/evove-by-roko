"""routine actions contributions

Revision ID: b2e7d9c4a6f1
Revises: f7b3e9c1d4a8
Create Date: 2026-09-08 09:10:00.000000

Inserts contributions for the routine actions from attributes_tree.json.
These cover the mobility branch (flexibilidade, estabilidade, c_mobilidade),
which no action reached before, plus the recurring mental and literacy
habits.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "b2e7d9c4a6f1"
down_revision: Union[str, None] = "f7b3e9c1d4a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_ACTIONS = (
    "ALONGAMENTO", "MOBILIDADE ARTICULAR", "AQUECIMENTO", "YOGA",
    "MEDITAÇÃO", "RESPIRAÇÃO",
    "DIÁRIO", "ESTUDO", "PODCAST",
)


def upgrade() -> None:
    seed_path = Path(__file__).resolve().parents[1] / "seeds" / "attributes_tree.pre_engine.json"
    with seed_path.open("r", encoding="utf-8") as f:
        seed = json.load(f)

    conn = op.get_bind()
    leaf_rows = conn.execute(sa.text("SELECT id, `key` FROM attr_nodes WHERE is_leaf=1")).fetchall()
    leaf_id = {r[1]: r[0] for r in leaf_rows}
    existing = {
        (r[0], r[1])
        for r in conn.execute(sa.text("SELECT action_name, leaf_id FROM action_contributions")).fetchall()
    }

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
        and c["leaf"] in leaf_id
        and (c["action"].upper(), leaf_id[c["leaf"]]) not in existing
    ]
    if rows:
        op.bulk_insert(contribs_tbl, rows)


def downgrade() -> None:
    keys = ",".join(f"'{a}'" for a in NEW_ACTIONS)
    op.execute(f"DELETE FROM action_contributions WHERE action_name IN ({keys})")
