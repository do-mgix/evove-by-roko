"""attribute tree (anatomy + neurology) with decay

Revision ID: b7c1d4e3f2a9
Revises: a844b8c6e2c0
Create Date: 2026-05-12 14:00:00.000000

Creates static tree (attr_nodes, attr_edges, action_contributions) and
per-user leaf score state (user_leaf_scores). Seeds the static tree from
backend/data/attributes_tree.json. Wipes legacy attribute data.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "b7c1d4e3f2a9"
down_revision: Union[str, None] = "a844b8c6e2c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_tree(conn):
    seed_path = Path(__file__).resolve().parents[2] / "data" / "attributes_tree.json"
    with seed_path.open("r", encoding="utf-8") as f:
        tree = json.load(f)

    nodes = sa.table(
        "attr_nodes",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("is_leaf", sa.Boolean),
        sa.column("half_life_hours", sa.Float),
        sa.column("floor", sa.Float),
        sa.column("threshold", sa.Float),
    )
    edges = sa.table(
        "attr_edges",
        sa.column("parent_id", sa.BigInteger),
        sa.column("child_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )
    contribs = sa.table(
        "action_contributions",
        sa.column("action_name", sa.String),
        sa.column("leaf_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )

    op.bulk_insert(nodes, [
        {
            "key": n["key"],
            "name": n["name"],
            "is_leaf": bool(n["is_leaf"]),
            "half_life_hours": n.get("half_life_hours"),
            "floor": n.get("floor"),
            "threshold": n.get("threshold"),
        }
        for n in tree["nodes"]
    ])

    rows = conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()
    id_by_key = {r[1]: r[0] for r in rows}

    op.bulk_insert(edges, [
        {
            "parent_id": id_by_key[e["parent"]],
            "child_id": id_by_key[e["child"]],
            "weight": float(e["weight"]),
        }
        for e in tree["edges"]
    ])

    op.bulk_insert(contribs, [
        {
            "action_name": c["action"].upper(),
            "leaf_id": id_by_key[c["leaf"]],
            "weight": float(c["weight"]),
        }
        for c in tree["contributions"]
    ])


def upgrade() -> None:
    op.create_table(
        "attr_nodes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_leaf", sa.Boolean(), nullable=False, default=False),
        sa.Column("half_life_hours", sa.Float(), nullable=True),
        sa.Column("floor", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
    )

    op.create_table(
        "attr_edges",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("child_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("weight", sa.Float(), nullable=False, default=0.0),
        sa.UniqueConstraint("parent_id", "child_id", name="uq_attr_edge_parent_child"),
    )

    op.create_table(
        "action_contributions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("action_name", sa.String(128), nullable=False, index=True),
        sa.Column("leaf_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("weight", sa.Float(), nullable=False, default=0.0),
        sa.UniqueConstraint("action_name", "leaf_id", name="uq_action_contrib_name_leaf"),
    )

    op.create_table(
        "user_leaf_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("leaf_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("score", sa.Float(), nullable=False, default=0.0),
        sa.Column("last_updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "leaf_id", name="uq_user_leaf"),
    )

    op.add_column("user_state", sa.Column("last_decay_check", sa.Date(), nullable=True))

    conn = op.get_bind()
    _seed_tree(conn)

    # Reset legacy attribute data
    op.execute("DELETE FROM attribute_actions")
    op.execute("DELETE FROM attributes")


def downgrade() -> None:
    op.drop_column("user_state", "last_decay_check")
    op.drop_table("user_leaf_scores")
    op.drop_table("action_contributions")
    op.drop_table("attr_edges")
    op.drop_table("attr_nodes")
