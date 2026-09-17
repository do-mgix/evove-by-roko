"""marks and ranks replace scores, levels and xp

Revision ID: f3b8d1e7a4c2
Revises: e2c7a9d4f6b1
Create Date: 2026-09-12 18:00:00.000000

Attributes leveled up without end and xp meant little. The unit is now the mark:
an act picks one of six tiers of its action, worth 0-5 marks, with at most 5 per
action every 6 hours (`mark_events` holds the window). Attributes move through
ranks A-Z; a rank is a permanent checkpoint and the marks above it are progress.
Continuous decay is gone.

- action_templates.tiers comes from the live seed;
- user_leaf_scores and user_attributes: score -> marks, permanent_level ->
  rank_index, zeroed — the old values are in another unit;
- user_state.marks and logs.marks are added; the xp columns stay as legacy;
- user_state.last_decay_check and attr_nodes floor/threshold/max_level go;
  half_life_hours stays for a future time-based loss.

`rank_index` and `option_index` avoid RANK and OPTION, reserved words in MySQL.
The downgrade restores shapes, not data.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "f3b8d1e7a4c2"
down_revision: Union[str, None] = "e2c7a9d4f6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HERE = Path(__file__).resolve()
# Frozen: reading the live seed here meant a later edit to it changed the tiers a
# fresh install was built with. The copy is the seed as it stood at this revision.
FROZEN_ENGINE = _HERE.parents[1] / "seeds" / "attributes_tree.engine.json"
FROZEN_TREE = _HERE.parents[1] / "seeds" / "attributes_tree.pre_engine.json"


def _load(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("action_templates", sa.Column("tiers", sa.JSON(), nullable=True))
    for t in _load(FROZEN_ENGINE)["action_templates"]:
        if t.get("tiers"):
            conn.execute(sa.text("UPDATE action_templates SET tiers = :j WHERE action_name = :n"),
                         {"j": json.dumps(t["tiers"], ensure_ascii=False), "n": t["action"].upper()})

    op.create_table(
        "mark_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engine_action_id", sa.String(16), nullable=False),
        sa.Column("action_id", sa.String(16), nullable=False),
        sa.Column("acted_at", sa.DateTime(), nullable=False),
        sa.Column("option_index", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("marks", sa.Integer(), nullable=False),
        sa.Index("ix_mark_events_window", "user_id", "engine_action_id", "acted_at"),
    )

    for table in ("user_leaf_scores", "user_attributes"):
        op.alter_column(table, "score", new_column_name="marks",
                        existing_type=sa.Float(), existing_nullable=False)
        op.alter_column(table, "permanent_level", new_column_name="rank_index",
                        existing_type=sa.Integer(), existing_nullable=False)
        conn.execute(sa.text(f"UPDATE {table} SET marks = 0, rank_index = 0"))

    op.add_column("user_state", sa.Column("marks", sa.Integer(), nullable=False, server_default="0"))
    op.drop_column("user_state", "last_decay_check")
    op.add_column("logs", sa.Column("marks", sa.Integer(), nullable=False, server_default="0"))

    for column in ("floor", "threshold", "max_level"):
        op.drop_column("attr_nodes", column)


def downgrade() -> None:
    conn = op.get_bind()

    op.add_column("attr_nodes", sa.Column("floor", sa.Float(), nullable=True))
    op.add_column("attr_nodes", sa.Column("threshold", sa.Float(), nullable=True))
    op.add_column("attr_nodes", sa.Column("max_level", sa.Integer(), nullable=True))
    for n in _load(FROZEN_TREE)["nodes"]:
        conn.execute(sa.text("UPDATE attr_nodes SET floor = :f, threshold = :t, max_level = :m WHERE `key` = :k"),
                     {"f": n.get("floor"), "t": n.get("threshold"), "m": n.get("max_level"), "k": n["key"]})

    op.drop_column("logs", "marks")
    op.add_column("user_state", sa.Column("last_decay_check", sa.Date(), nullable=True))
    op.drop_column("user_state", "marks")

    for table in ("user_leaf_scores", "user_attributes"):
        conn.execute(sa.text(f"UPDATE {table} SET marks = 0, rank_index = 0"))
        op.alter_column(table, "rank_index", new_column_name="permanent_level",
                        existing_type=sa.Integer(), existing_nullable=False)
        op.alter_column(table, "marks", new_column_name="score",
                        existing_type=sa.Float(), existing_nullable=False)

    op.drop_table("mark_events")
    op.drop_column("action_templates", "tiers")
