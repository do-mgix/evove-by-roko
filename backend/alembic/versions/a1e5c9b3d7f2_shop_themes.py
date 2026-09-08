"""conceptual themes for the actions that had none

Revision ID: a1e5c9b3d7f2
Revises: f9d3b6e8a2c4
Create Date: 2026-09-08 13:30:00.000000

The shop files each action under the parent of its heaviest conceptual leaf.
Twenty actions had no conceptual contribution at all and fell back to an
anatomical region, so the catalog mixed themes (Treino, Escrita) with body
parts (Sensorial, Sistema Límbico). Adds Alimentação, Consumo and Prática
Mental with their leaves, and files those twenty under them.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "a1e5c9b3d7f2"
down_revision: Union[str, None] = "f9d3b6e8a2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


THEME_KEYS = {
    "c_alimentacao", "c_refeicao", "c_bebida",
    "c_consumo", "c_redes", "c_video", "c_jogos", "c_audio", "c_indulgencia",
    "c_pratica_mental", "c_meditacao", "c_escuta", "c_raciocinio",
}


def upgrade() -> None:
    seed_path = Path(__file__).resolve().parents[2] / "data" / "attributes_tree.json"
    with seed_path.open("r", encoding="utf-8") as f:
        tree = json.load(f)

    conn = op.get_bind()
    existing_keys = {r[0] for r in conn.execute(sa.text("SELECT `key` FROM attr_nodes")).fetchall()}

    nodes_tbl = sa.table(
        "attr_nodes",
        sa.column("key", sa.String), sa.column("name", sa.String),
        sa.column("is_leaf", sa.Boolean), sa.column("half_life_hours", sa.Float),
        sa.column("floor", sa.Float), sa.column("threshold", sa.Float),
        sa.column("max_level", sa.Integer), sa.column("tree_kind", sa.String),
    )
    op.bulk_insert(nodes_tbl, [
        {
            "key": n["key"], "name": n["name"], "is_leaf": bool(n["is_leaf"]),
            "half_life_hours": n.get("half_life_hours"), "floor": n.get("floor"),
            "threshold": n.get("threshold"), "max_level": n.get("max_level"),
            "tree_kind": "conceptual",
        }
        for n in tree["nodes"]
        if n["key"] in THEME_KEYS and n["key"] not in existing_keys
    ])

    id_by_key = {r[1]: r[0] for r in conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()}

    existing_edges = {
        (r[0], r[1])
        for r in conn.execute(sa.text("SELECT parent_id, child_id FROM attr_edges")).fetchall()
    }
    edges_tbl = sa.table(
        "attr_edges",
        sa.column("parent_id", sa.BigInteger), sa.column("child_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )
    op.bulk_insert(edges_tbl, [
        {"parent_id": id_by_key[e["parent"]], "child_id": id_by_key[e["child"]], "weight": float(e["weight"])}
        for e in tree["edges"]
        if e["parent"] in THEME_KEYS
        and (id_by_key[e["parent"]], id_by_key[e["child"]]) not in existing_edges
    ])

    existing_contribs = {
        (r[0], r[1])
        for r in conn.execute(sa.text("SELECT action_name, leaf_id FROM action_contributions")).fetchall()
    }
    contribs_tbl = sa.table(
        "action_contributions",
        sa.column("action_name", sa.String), sa.column("leaf_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )
    op.bulk_insert(contribs_tbl, [
        {"action_name": c["action"].upper(), "leaf_id": id_by_key[c["leaf"]], "weight": float(c["weight"])}
        for c in tree["contributions"]
        if c["leaf"] in THEME_KEYS
        and (c["action"].upper(), id_by_key[c["leaf"]]) not in existing_contribs
    ])


def downgrade() -> None:
    keys = ",".join(f"'{k}'" for k in sorted(THEME_KEYS))
    op.execute(f"""
        DELETE FROM action_contributions
        WHERE leaf_id IN (SELECT id FROM attr_nodes WHERE `key` IN ({keys}))
    """)
    op.execute(f"""
        DELETE FROM attr_edges
        WHERE parent_id IN (SELECT id FROM attr_nodes WHERE `key` IN ({keys}))
           OR child_id  IN (SELECT id FROM attr_nodes WHERE `key` IN ({keys}))
    """)
    op.execute(f"DELETE FROM attr_nodes WHERE `key` IN ({keys})")
