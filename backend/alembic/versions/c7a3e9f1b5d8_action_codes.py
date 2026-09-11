"""memorable action ids: 5aa-aa-ii

Revision ID: c7a3e9f1b5d8
Revises: b4f7d2a9e6c3
Create Date: 2026-09-10 12:00:00.000000

Action ids were per-profile counters starting at 501, so the same action had a
different number for everyone and none of them meant anything. They become
the catalog code: 5, the parent conceptual class, the child class and the
action's position in it — FLEXÃO is 5010108 for every profile.

Codes are read from attributes_tree.json, where they were assigned once. They
are stored, never recomputed: deriving them from contributions at runtime
would let a weight change renumber an action.

Existing actions are renamed to their code, and the references that hold an
action id — agenda labels, project and attribute links — are rewritten with
them. An action with no catalog template keeps the id it has.
"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = "c7a3e9f1b5d8"
down_revision: Union[str, None] = "b4f7d2a9e6c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attr_nodes", sa.Column("code", sa.String(2), nullable=True))
    op.add_column("action_templates", sa.Column("code", sa.String(7), nullable=True))

    seed_path = Path(__file__).resolve().parents[2] / "data" / "attributes_tree.json"
    with seed_path.open("r", encoding="utf-8") as f:
        seed = json.load(f)

    conn = op.get_bind()

    for n in seed["nodes"]:
        if n.get("code"):
            conn.execute(sa.text("UPDATE attr_nodes SET code = :c WHERE `key` = :k"),
                         {"c": n["code"], "k": n["key"]})

    codes = {t["action"].upper(): t["code"] for t in seed["action_templates"]}
    if len(set(codes.values())) != len(codes):
        raise RuntimeError("attributes_tree.json has duplicate action codes")
    for name, code in codes.items():
        conn.execute(sa.text("UPDATE action_templates SET code = :c WHERE action_name = :n"),
                     {"c": code, "n": name})

    missing = conn.execute(sa.text("SELECT action_name FROM action_templates WHERE code IS NULL")).fetchall()
    if missing:
        raise RuntimeError(f"templates without a code in the seed: {[r[0] for r in missing]}")

    op.alter_column("action_templates", "code", existing_type=sa.String(7), nullable=False)
    op.create_unique_constraint("uq_action_templates_code", "action_templates", ["code"])

    # ---- move owned actions onto their codes ----
    rows = conn.execute(sa.text("""
        SELECT a.id, a.user_id, a.action_id, t.code
        FROM actions a
        JOIN action_templates t ON t.action_name = a.name
        WHERE a.action_id <> t.code
    """)).fetchall()

    for pk, user_id, old, new in rows:
        params = {"uid": user_id, "old": old, "new": new}
        conn.execute(sa.text("""
            UPDATE agenda_items SET label_id = :new
            WHERE user_id = :uid AND label_kind = 'action' AND label_id = :old
        """), params)
        conn.execute(sa.text("""
            UPDATE project_actions pa JOIN projects p ON p.id = pa.project_pk
            SET pa.action_id = :new
            WHERE p.user_id = :uid AND pa.action_id = :old
        """), params)
        conn.execute(sa.text("""
            UPDATE attribute_actions aa JOIN attributes at ON at.id = aa.attribute_pk
            SET aa.action_id = :new
            WHERE at.user_id = :uid AND aa.action_id = :old
        """), params)
        conn.execute(sa.text("UPDATE actions SET action_id = :new WHERE id = :pk"),
                     {"new": new, "pk": pk})


def downgrade() -> None:
    # Owned actions keep their codes as ids: the counters they replaced carried
    # no information worth rebuilding, and a 7-digit string is still a valid id.
    op.drop_constraint("uq_action_templates_code", "action_templates", type_="unique")
    op.drop_column("action_templates", "code")
    op.drop_column("attr_nodes", "code")
