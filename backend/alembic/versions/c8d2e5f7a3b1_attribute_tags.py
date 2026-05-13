"""attribute tags (composite summary)

Revision ID: c8d2e5f7a3b1
Revises: b7c1d4e3f2a9
Create Date: 2026-05-12 16:00:00.000000

Creates static curated tags (attribute_tags + attribute_tag_sources) and
seeds them from backend/data/attribute_tags.json.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "c8d2e5f7a3b1"
down_revision: Union[str, None] = "b7c1d4e3f2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_tags(conn):
    seed_path = Path(__file__).resolve().parents[2] / "data" / "attribute_tags.json"
    with seed_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    leaf_rows = conn.execute(sa.text("SELECT id, `key` FROM attr_nodes WHERE is_leaf=1")).fetchall()
    leaf_id_by_key = {r[1]: r[0] for r in leaf_rows}

    tags_tbl = sa.table(
        "attribute_tags",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("display_order", sa.Integer),
    )
    sources_tbl = sa.table(
        "attribute_tag_sources",
        sa.column("tag_id", sa.BigInteger),
        sa.column("leaf_id", sa.BigInteger),
        sa.column("weight", sa.Float),
    )

    op.bulk_insert(tags_tbl, [
        {
            "key": t["key"],
            "name": t["name"],
            "category": t["category"],
            "display_order": int(t["display_order"]),
        }
        for t in data["tags"]
    ])

    tag_rows = conn.execute(sa.text("SELECT id, `key` FROM attribute_tags")).fetchall()
    tag_id_by_key = {r[1]: r[0] for r in tag_rows}

    sources = []
    for t in data["tags"]:
        for s in t["sources"]:
            sources.append({
                "tag_id": tag_id_by_key[t["key"]],
                "leaf_id": leaf_id_by_key[s["leaf"]],
                "weight": float(s["weight"]),
            })
    op.bulk_insert(sources_tbl, sources)


def upgrade() -> None:
    op.create_table(
        "attribute_tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, default=0),
    )
    op.create_table(
        "attribute_tag_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tag_id", sa.BigInteger(), sa.ForeignKey("attribute_tags.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("leaf_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("weight", sa.Float(), nullable=False, default=0.0),
        sa.UniqueConstraint("tag_id", "leaf_id", name="uq_tag_source"),
    )
    conn = op.get_bind()
    _seed_tags(conn)


def downgrade() -> None:
    op.drop_table("attribute_tag_sources")
    op.drop_table("attribute_tags")
