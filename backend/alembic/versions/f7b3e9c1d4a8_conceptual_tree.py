"""conceptual attribute tree

Revision ID: f7b3e9c1d4a8
Revises: e5a1c9d8b2f4
Create Date: 2026-05-12 20:00:00.000000

Adds `tree_kind` column to attr_nodes and seeds the conceptual tree
(Treino, Literacia, Programação + sub-folhas) plus contributions linking
existing and new actions to conceptual leaves.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "f7b3e9c1d4a8"
down_revision: Union[str, None] = "e5a1c9d8b2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attr_nodes",
        sa.Column("tree_kind", sa.String(16), nullable=False, server_default="anatomical"),
    )

    seed_path = Path(__file__).resolve().parents[2] / "data" / "attributes_tree.json"
    with seed_path.open("r", encoding="utf-8") as f:
        tree = json.load(f)

    conceptual_nodes = [n for n in tree["nodes"] if n.get("tree_kind") == "conceptual"]
    conceptual_keys = {n["key"] for n in conceptual_nodes}

    nodes_tbl = sa.table(
        "attr_nodes",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("is_leaf", sa.Boolean),
        sa.column("half_life_hours", sa.Float),
        sa.column("floor", sa.Float),
        sa.column("threshold", sa.Float),
        sa.column("max_level", sa.Integer),
        sa.column("tree_kind", sa.String),
    )
    op.bulk_insert(nodes_tbl, [
        {
            "key": n["key"],
            "name": n["name"],
            "is_leaf": bool(n["is_leaf"]),
            "half_life_hours": n.get("half_life_hours"),
            "floor": n.get("floor"),
            "threshold": n.get("threshold"),
            "max_level": n.get("max_level"),
            "tree_kind": "conceptual",
        }
        for n in conceptual_nodes
    ])

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()
    id_by_key = {r[1]: r[0] for r in rows}

    edges_tbl = sa.table(
        "attr_edges",
        sa.column("parent_id", sa.BigInteger),
        sa.column("child_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )
    new_edges = [
        e for e in tree["edges"]
        if e["parent"] in conceptual_keys or e["child"] in conceptual_keys
    ]
    op.bulk_insert(edges_tbl, [
        {
            "parent_id": id_by_key[e["parent"]],
            "child_id": id_by_key[e["child"]],
            "weight": float(e["weight"]),
        }
        for e in new_edges
    ])

    contribs_tbl = sa.table(
        "action_contributions",
        sa.column("action_name", sa.String),
        sa.column("leaf_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )
    # Insert: any contribution mentioning a conceptual leaf, OR for the 4 new escrita actions
    new_actions = {"ESCREVER DIÁLOGOS", "ESCREVER DESCRIÇÕES", "ESCREVER NARRATIVA", "ESCREVER ARGUMENTAÇÃO"}
    rows_to_insert = []
    for c in tree["contributions"]:
        action = c["action"]
        leaf = c["leaf"]
        is_conceptual_leaf = leaf in conceptual_keys
        is_new_action = action in new_actions
        if not (is_conceptual_leaf or is_new_action):
            continue
        rows_to_insert.append({
            "action_name": action.upper(),
            "leaf_id": id_by_key[leaf],
            "weight": float(c["weight"]),
        })
    if rows_to_insert:
        op.bulk_insert(contribs_tbl, rows_to_insert)


def downgrade() -> None:
    op.execute("""
        DELETE FROM action_contributions
        WHERE leaf_id IN (SELECT id FROM attr_nodes WHERE tree_kind = 'conceptual')
    """)
    op.execute("""
        DELETE FROM action_contributions
        WHERE action_name IN ('ESCREVER DIÁLOGOS', 'ESCREVER DESCRIÇÕES', 'ESCREVER NARRATIVA', 'ESCREVER ARGUMENTAÇÃO')
    """)
    op.execute("""
        DELETE FROM attr_edges
        WHERE parent_id IN (SELECT id FROM attr_nodes WHERE tree_kind = 'conceptual')
           OR child_id IN (SELECT id FROM attr_nodes WHERE tree_kind = 'conceptual')
    """)
    op.execute("DELETE FROM attr_nodes WHERE tree_kind = 'conceptual'")
    op.drop_column("attr_nodes", "tree_kind")
