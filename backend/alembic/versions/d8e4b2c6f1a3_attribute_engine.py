"""attribute engine: one graph, no kinds

Revision ID: d8e4b2c6f1a3
Revises: c7a3e9f1b5d8
Create Date: 2026-09-11 10:00:00.000000

Attributes were three kinds with their own code paths: anatomical nodes,
conceptual nodes (attr_nodes.tree_kind) and tags, a side table of weighted
leaf lists. They become one graph. Every attribute is the same kind of thing,
any of them can have weighted children, a leaf is simply a node without
children, and a node may have several parents, one of them primary — the
chain that defines its degree.

- tags become nodes (t_*) under two new roots, Físico and Mental, drawing on
  their leaves through non-primary links with the same weights, so every
  tag keeps the value it had;
- every node's decay and level settings are synced from the seed, which fixes
  the 17 conceptual leaves b7c1 created before max_level existed;
- is_leaf, tree_kind and attr_nodes.code are dropped; shop_group marks the
  practice roots the shop groups by, and nothing else reads it;
- each action is registered under a parent attribute, and codes are
  re-derived from it: 5 · class1 · class2 · position, with class1 the
  ancestor at degree max(2, ceil(N/2)) and class2 the parent itself. The class
  numbers are stored in id_class1 / id_class2.

Owned actions and the references that hold their id are renamed in two passes:
old and new codes share one 7-digit space, so a direct rename could land on a
code another action still holds.
"""
from typing import Sequence, Union
from pathlib import Path
import json
import math

from alembic import op
import sqlalchemy as sa


revision: str = "d8e4b2c6f1a3"
down_revision: Union[str, None] = "c7a3e9f1b5d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HERE = Path(__file__).resolve()
LIVE_SEED = _HERE.parents[2] / "data" / "attributes_tree.json"
FROZEN_TREE = _HERE.parents[1] / "seeds" / "attributes_tree.pre_engine.json"
FROZEN_TAGS = _HERE.parents[1] / "seeds" / "attribute_tags.pre_engine.json"
PARAMS = ("half_life_hours", "floor", "threshold", "max_level")


def _load(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ids(conn):
    return {r[1]: r[0] for r in conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()}


def _rename_owned(conn, code_by_name):
    """Move owned actions (and the ids stored elsewhere) onto `code_by_name`."""
    rows = conn.execute(sa.text("SELECT id, user_id, action_id, name FROM actions")).fetchall()
    moves = [(pk, uid, old, code_by_name[name]) for pk, uid, old, name in rows
             if name in code_by_name and old != code_by_name[name]]

    def retarget(uid, src, dst):
        p = {"uid": uid, "src": src, "dst": dst}
        conn.execute(sa.text("""UPDATE agenda_items SET label_id = :dst
            WHERE user_id = :uid AND label_kind = 'action' AND label_id = :src"""), p)
        conn.execute(sa.text("""UPDATE project_actions pa JOIN projects p ON p.id = pa.project_pk
            SET pa.action_id = :dst WHERE p.user_id = :uid AND pa.action_id = :src"""), p)
        conn.execute(sa.text("""UPDATE attribute_actions aa JOIN attributes at ON at.id = aa.attribute_pk
            SET aa.action_id = :dst WHERE at.user_id = :uid AND aa.action_id = :src"""), p)

    for pk, uid, old, _new in moves:              # pass 1: park every mover
        retarget(uid, old, "~" + old)
        conn.execute(sa.text("UPDATE actions SET action_id = :v WHERE id = :pk"), {"v": "~" + old, "pk": pk})
    for pk, uid, old, new in moves:               # pass 2: land on the new code
        retarget(uid, "~" + old, new)
        conn.execute(sa.text("UPDATE actions SET action_id = :v WHERE id = :pk"), {"v": new, "pk": pk})


def _restore_template_codes(conn, code_by_name):
    op.drop_constraint("uq_action_templates_code", "action_templates", type_="unique")
    for name, code in code_by_name.items():
        conn.execute(sa.text("UPDATE action_templates SET code = :c WHERE action_name = :n"),
                     {"c": code, "n": name})
    op.create_unique_constraint("uq_action_templates_code", "action_templates", ["code"])


def upgrade() -> None:
    seed = _load(LIVE_SEED)
    conn = op.get_bind()

    # ---- shape ----
    op.add_column("attr_edges", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("attr_nodes", sa.Column("shop_group", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.drop_column("attr_nodes", "is_leaf")
    op.drop_column("attr_nodes", "tree_kind")
    op.drop_column("attr_nodes", "code")

    # ---- nodes: add the missing ones, sync every node's settings ----
    ids = _ids(conn)
    for n in seed["nodes"]:
        vals = {"k": n["key"], "name": n["name"], "sg": bool(n.get("shop_group", False)),
                **{p: n.get(p) for p in PARAMS}}
        if n["key"] in ids:
            conn.execute(sa.text("""UPDATE attr_nodes SET name = :name, half_life_hours = :half_life_hours,
                floor = :floor, threshold = :threshold, max_level = :max_level, shop_group = :sg
                WHERE `key` = :k"""), vals)
        else:
            conn.execute(sa.text("""INSERT INTO attr_nodes
                (`key`, name, half_life_hours, floor, threshold, max_level, shop_group)
                VALUES (:k, :name, :half_life_hours, :floor, :threshold, :max_level, :sg)"""), vals)
    ids = _ids(conn)

    # ---- edges ----
    existing = {(r[0], r[1]) for r in conn.execute(sa.text("SELECT parent_id, child_id FROM attr_edges")).fetchall()}
    for e in seed["edges"]:
        p = {"pid": ids[e["parent"]], "cid": ids[e["child"]], "w": float(e["weight"]),
             "prim": bool(e.get("primary", True))}
        if (p["pid"], p["cid"]) in existing:
            conn.execute(sa.text("""UPDATE attr_edges SET weight = :w, is_primary = :prim
                WHERE parent_id = :pid AND child_id = :cid"""), p)
        else:
            conn.execute(sa.text("""INSERT INTO attr_edges (parent_id, child_id, weight, is_primary)
                VALUES (:pid, :cid, :w, :prim)"""), p)

    prim = {}
    for cid, pid in conn.execute(sa.text("SELECT child_id, parent_id FROM attr_edges WHERE is_primary")).fetchall():
        if cid in prim:
            raise RuntimeError(f"node {cid} has two primary parents")
        prim[cid] = pid

    # ---- contributions mirror the seed ----
    # A later subdivision moves contributions from a parent to its children in the
    # seed; this is what reproduces that on a fresh install.
    want = {(c["action"].upper(), ids[c["leaf"]]): float(c["weight"]) for c in seed["contributions"]}
    have = {(r[1], r[2]): (r[0], r[3]) for r in conn.execute(sa.text(
        "SELECT id, action_name, leaf_id, weight FROM action_contributions")).fetchall()}
    for key, (rid, _w) in have.items():
        if key not in want:
            conn.execute(sa.text("DELETE FROM action_contributions WHERE id = :i"), {"i": rid})
    for (name, leaf), w in want.items():
        if (name, leaf) not in have:
            conn.execute(sa.text("INSERT INTO action_contributions (action_name, leaf_id, weight) VALUES (:n, :l, :w)"),
                         {"n": name, "l": leaf, "w": w})
        elif abs(have[(name, leaf)][1] - w) > 1e-9:
            conn.execute(sa.text("UPDATE action_contributions SET weight = :w WHERE id = :i"),
                         {"w": w, "i": have[(name, leaf)][0]})

    # ---- tags are nodes now ----
    op.drop_table("attribute_tag_sources")
    op.drop_table("attribute_tags")

    # ---- action parents, class registries, codes ----
    op.create_table(
        "id_class1",
        sa.Column("node_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("code", sa.String(2), nullable=False, unique=True),
    )
    op.create_table(
        "id_class2",
        sa.Column("class1_node_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("node_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("code", sa.String(2), nullable=False),
        sa.UniqueConstraint("class1_node_id", "code", name="uq_id_class2_code"),
    )
    op.add_column("action_templates", sa.Column("parent_node_id", sa.BigInteger(), nullable=True))

    def chain(nid):
        out = [nid]
        while out[-1] in prim:
            out.append(prim[out[-1]])
            if len(out) > 64:
                raise RuntimeError("primary chain loops")
        return list(reversed(out))

    code_by_name, parent_by_name, c1, c2 = {}, {}, {}, {}
    for t in seed["action_templates"]:
        name, code, parent = t["action"].upper(), t["code"], t["parent"]
        ch = chain(ids[parent])
        if len(ch) < 2:
            raise RuntimeError(f"{name}: parent {parent} is a root")
        s1 = ch[max(2, math.ceil(len(ch) / 2)) - 1]
        s2 = None if s1 == ids[parent] else ids[parent]
        for reg, key, val in ((c1, s1, code[1:3]), (c2, (s1, s2), code[3:5])):
            if reg.setdefault(key, val) != val:
                raise RuntimeError(f"{name}: {code} disagrees with an earlier class number")
        if s2 is None and code[3:5] != "00":
            raise RuntimeError(f"{name}: class2 must be 00 when the parent is the class1 itself")
        code_by_name[name], parent_by_name[name] = code, parent
    if len(set(c1.values())) != len(c1):
        raise RuntimeError("two class1 attributes share a number")
    for s1 in c1:
        nums = [v for (a, b), v in c2.items() if a == s1 and b is not None]
        if len(set(nums)) != len(nums):
            raise RuntimeError("two class2 attributes share a number under one class1")

    for node, code in c1.items():
        conn.execute(sa.text("INSERT INTO id_class1 (node_id, code) VALUES (:n, :c)"), {"n": node, "c": code})
    for (s1, s2), code in c2.items():
        if s2 is not None:
            conn.execute(sa.text("INSERT INTO id_class2 (class1_node_id, node_id, code) VALUES (:a, :b, :c)"),
                         {"a": s1, "b": s2, "c": code})

    known = {r[0] for r in conn.execute(sa.text("SELECT action_name FROM action_templates")).fetchall()}
    op.drop_constraint("uq_action_templates_code", "action_templates", type_="unique")
    for t in seed["action_templates"]:
        name = t["action"].upper()
        vals = {"n": name, "c": t["code"], "p": ids[t["parent"]], "ty": int(t.get("type", 0)),
                "d": int(t.get("diff", 1)), "co": int(t.get("cost", 0)),
                "tc": int(t.get("token_cost", 0)), "tg": int(t.get("token_gain", 0))}
        if name in known:
            conn.execute(sa.text("UPDATE action_templates SET code = :c, parent_node_id = :p WHERE action_name = :n"), vals)
        else:
            conn.execute(sa.text("""INSERT INTO action_templates
                (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain)
                VALUES (:n, :c, :p, :ty, :d, :co, :tc, :tg)"""), vals)
    op.create_unique_constraint("uq_action_templates_code", "action_templates", ["code"])
    missing = conn.execute(sa.text("SELECT action_name FROM action_templates WHERE parent_node_id IS NULL")).fetchall()
    if missing:
        raise RuntimeError(f"templates with no parent in the seed: {[r[0] for r in missing]}")
    op.alter_column("action_templates", "parent_node_id", existing_type=sa.BigInteger(), nullable=False)
    op.create_foreign_key("fk_action_templates_parent", "action_templates", "attr_nodes",
                          ["parent_node_id"], ["id"])

    _rename_owned(conn, code_by_name)


def downgrade() -> None:
    tree = _load(FROZEN_TREE)
    tags = _load(FROZEN_TAGS)["tags"]
    conn = op.get_bind()

    old_codes = {t["action"].upper(): t["code"] for t in tree["action_templates"]}
    _rename_owned(conn, old_codes)
    op.drop_constraint("fk_action_templates_parent", "action_templates", type_="foreignkey")
    op.drop_column("action_templates", "parent_node_id")
    frozen_names = set(old_codes)
    for (name,) in conn.execute(sa.text("SELECT action_name FROM action_templates")).fetchall():
        if name not in frozen_names:
            conn.execute(sa.text("DELETE FROM action_templates WHERE action_name = :n"), {"n": name})
    _restore_template_codes(conn, old_codes)
    op.drop_table("id_class2")
    op.drop_table("id_class1")

    # contributions as they were
    ids = _ids(conn)
    conn.execute(sa.text("DELETE FROM action_contributions"))
    for c in tree["contributions"]:
        conn.execute(sa.text("INSERT INTO action_contributions (action_name, leaf_id, weight) VALUES (:n, :l, :w)"),
                     {"n": c["action"].upper(), "l": ids[c["leaf"]], "w": float(c["weight"])})

    # nodes that did not exist before the engine
    frozen_keys = {n["key"] for n in tree["nodes"]}
    extra = [k for k in _ids(conn) if k not in frozen_keys]
    for k in extra:
        conn.execute(sa.text("DELETE FROM attr_nodes WHERE `key` = :k"), {"k": k})

    op.create_table(
        "attribute_tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "attribute_tag_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tag_id", sa.BigInteger(), sa.ForeignKey("attribute_tags.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("leaf_id", sa.BigInteger(), sa.ForeignKey("attr_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tag_id", "leaf_id", name="uq_tag_source"),
    )
    ids = _ids(conn)
    for t in tags:
        r = conn.execute(sa.text("""INSERT INTO attribute_tags (`key`, name, category, display_order)
            VALUES (:k, :n, :c, :o)"""), {"k": t["key"], "n": t["name"], "c": t["category"], "o": t["display_order"]})
        for s in t["sources"]:
            conn.execute(sa.text("INSERT INTO attribute_tag_sources (tag_id, leaf_id, weight) VALUES (:t, :l, :w)"),
                         {"t": r.lastrowid, "l": ids[s["leaf"]], "w": s["weight"]})

    op.add_column("attr_nodes", sa.Column("code", sa.String(2), nullable=True))
    op.add_column("attr_nodes", sa.Column("tree_kind", sa.String(16), nullable=False, server_default="anatomical"))
    op.add_column("attr_nodes", sa.Column("is_leaf", sa.Boolean(), nullable=False, server_default=sa.false()))
    for n in tree["nodes"]:
        conn.execute(sa.text("""UPDATE attr_nodes SET is_leaf = :l, tree_kind = :tk, code = :c WHERE `key` = :k"""),
                     {"l": bool(n["is_leaf"]), "tk": n.get("tree_kind", "anatomical"), "c": n.get("code"), "k": n["key"]})
    op.drop_column("attr_nodes", "shop_group")
    op.drop_column("attr_edges", "is_primary")
