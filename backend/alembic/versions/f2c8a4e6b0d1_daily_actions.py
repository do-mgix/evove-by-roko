"""daily actions: what an ordinary day is made of

Revision ID: f2c8a4e6b0d1
Revises: d9b1c3e5f7a9
Create Date: 2026-10-21 09:00:00.000000

The catalog covered training, writing, programming and a few mental practices,
and left out most of what a day holds. Twenty-three actions fill it, each one
atomic — a single activity, generic, with no brand, no sport and no variant in
the name. Anything finer is a patch: PULAR CORDA · DUPLO, TOCAR INSTRUMENTO ·
VIOLÃO, LIMPEZA · BANHEIRO, CONVERSA · LIGAÇÃO.

- strength, one exercise per muscle the catalog could not reach: no action was
  registered under tríceps, bíceps, panturrilha, glúteo, lombar or posterior de
  coxa. MERGULHO, ROSCA, ELEVAÇÃO DE PANTURRILHA, PONTE DE GLÚTEO, EXTENSÃO
  LOMBAR and LEVANTAMENTO TERRA, plus SUPINO and SUSPENSÃO NA BARRA. They are
  filed under Calistenia with the rest of the strength work (DESENVOLVIMENTO and
  REMADA already are), so the graph gains no Musculação practice for them;
- cardio: PULAR CORDA, SUBIR ESCADAS and DANÇA, the last registered under
  coordenação, which opens class `09 02`;
- the mind: PLANEJAMENTO and QUEBRA-CABEÇA under Raciocínio, CONVERSA under
  Escuta;
- the arts are, in practice, completely different from anything in the graph,
  so they get a practice root of their own: Artes, with Música (TOCAR
  INSTRUMENTO, CANTO) and Artes Visuais (DESENHO). Like every practice root it
  is a shop section and nothing else reads its mark;
- six log actions, neutral like ÔNIBUS and TRABALHO — the day's ledger, no
  attribute, no tokens either way: SONO, LIMPEZA, COZINHAR, LAVAR ROUPA,
  COMPRAS, DIRIGIR. Cooking is a chore here, not a meal: nothing about what is
  eaten enters the graph.

Prices follow the economy after `a2f4`: 300, 500 or 800 points by difficulty,
releasing 1 to 3 tokens. Codes skip every position some earlier action held
(5020101 and 5020105 were BASQUETE and FUTEBOL), so no new id inherits an old
one's history.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2c8a4e6b0d1"
down_revision: Union[str, None] = "d9b1c3e5f7a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# key, name, (parent, weight) — the new practice root and its two leaves
ARTS_ROOT = ("c_artes", "Artes")
ARTS_LEAVES = [("c_musica", "Música", 0.5), ("c_artes_visuais", "Artes Visuais", 0.5)]

# class2 numbers the new parents open: class1 key -> [(parent key, code)]
NEW_CLASS2 = {
    "musculatura": [("triceps", "07"), ("panturrilha", "08"), ("gluteo", "09"),
                    ("lombar", "10"), ("biceps", "11"), ("posterior_coxa", "12")],
    "cerebelo": [("coordenacao", "02")],
}

# name, code, parent, diff, cost, token_gain, tiers, {leaf: weight}
TRAINED = [
    ("MERGULHO", "5010701", "triceps", 2, 500, 2, {"unit": "reps", "bounds": [5, 15, 30, 50, 80]},
     {"triceps": 0.45, "peitoral": 0.3, "deltoide": 0.25, "c_calistenia": 1.0}),
    ("ELEVAÇÃO DE PANTURRILHA", "5010801", "panturrilha", 1, 300, 1, {"unit": "reps", "bounds": [20, 50, 100, 150, 250]},
     {"panturrilha": 0.85, "equilibrio": 0.15, "c_calistenia": 1.0}),
    ("PONTE DE GLÚTEO", "5010901", "gluteo", 1, 300, 1, {"unit": "reps", "bounds": [15, 40, 80, 120, 200]},
     {"gluteo": 0.6, "posterior_coxa": 0.25, "lombar": 0.15, "c_calistenia": 1.0}),
    ("EXTENSÃO LOMBAR", "5011001", "lombar", 1, 300, 1, {"unit": "reps", "bounds": [10, 30, 60, 100, 150]},
     {"lombar": 0.6, "gluteo": 0.2, "posterior_coxa": 0.2, "c_calistenia": 1.0}),
    ("ROSCA", "5011101", "biceps", 1, 300, 1, {"unit": "reps", "bounds": [10, 30, 60, 100, 150]},
     {"biceps": 0.7, "antebraco": 0.3, "c_calistenia": 1.0}),
    ("LEVANTAMENTO TERRA", "5011201", "posterior_coxa", 3, 800, 3, {"unit": "reps", "bounds": [5, 15, 30, 50, 80]},
     {"posterior_coxa": 0.3, "gluteo": 0.25, "lombar": 0.2, "dorsal": 0.1, "antebraco": 0.1, "quadriceps": 0.05,
      "c_calistenia": 1.0}),
    ("SUSPENSÃO NA BARRA", "5010205", "antebraco", 1, 300, 1, {"unit": "s", "bounds": [15, 30, 60, 120, 180]},
     {"antebraco": 0.6, "dorsal": 0.2, "deltoide": 0.2, "c_calistenia": 1.0}),
    ("SUPINO", "5010307", "peitoral", 2, 500, 2, {"unit": "reps", "bounds": [10, 30, 60, 100, 150]},
     {"peitoral": 0.55, "triceps": 0.25, "deltoide": 0.2, "c_calistenia": 1.0}),
    ("PULAR CORDA", "5020108", "aerobico", 2, 500, 2, {"unit": "min", "bounds": [2, 5, 10, 20, 30]},
     {"aerobico": 0.4, "panturrilha": 0.25, "coordenacao": 0.2, "anaerobico": 0.15, "c_cardio": 1.0}),
    ("SUBIR ESCADAS", "5020109", "aerobico", 1, 300, 1, {"unit": "andares", "bounds": [3, 10, 20, 40, 60]},
     {"aerobico": 0.4, "quadriceps": 0.25, "gluteo": 0.2, "panturrilha": 0.15, "c_cardio": 1.0}),
    ("DANÇA", "5090201", "coordenacao", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 90]},
     {"coordenacao": 0.3, "aerobico": 0.25, "equilibrio": 0.15, "auditivo": 0.1, "quadriceps": 0.1,
      "panturrilha": 0.1, "c_cardio": 0.6, "c_esportes": 0.4}),
    ("PLANEJAMENTO", "5050210", "executiva", 1, 300, 1, {"unit": "min", "bounds": [5, 10, 20, 30, 60]},
     {"executiva": 0.5, "foco": 0.25, "hipocampo": 0.15, "broca": 0.1, "c_raciocinio": 1.0}),
    ("QUEBRA-CABEÇA", "5050211", "executiva", 1, 300, 1, {"unit": "min", "bounds": [10, 20, 40, 60, 90]},
     {"executiva": 0.35, "visual": 0.25, "foco": 0.25, "hipocampo": 0.15, "c_raciocinio": 1.0}),
    ("CONVERSA", "5080203", "wernicke", 1, 300, 1, {"unit": "min", "bounds": [10, 20, 40, 60, 120]},
     {"wernicke": 0.35, "broca": 0.3, "amigdala": 0.2, "recompensa": 0.15, "c_escuta": 1.0}),
    ("TOCAR INSTRUMENTO", "5070203", "auditivo", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 120]},
     {"auditivo": 0.3, "coordenacao": 0.25, "somatossensorial": 0.2, "foco": 0.15, "hipocampo": 0.1,
      "c_musica": 1.0}),
    ("CANTO", "5070204", "auditivo", 1, 300, 1, {"unit": "min", "bounds": [5, 10, 20, 40, 60]},
     {"auditivo": 0.4, "broca": 0.3, "recompensa": 0.15, "amigdala": 0.15, "c_musica": 1.0}),
    ("DESENHO", "5070107", "visual", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 120]},
     {"visual": 0.4, "coordenacao": 0.25, "foco": 0.2, "somatossensorial": 0.15, "c_artes_visuais": 1.0}),
]

# name, code, tiers — log actions: no parent, no contributions, no tokens
LOGGED = [
    ("SONO", "5000008", {"unit": "h", "bounds": [4, 5, 6, 7, 8]}),
    ("LIMPEZA", "5000009", {"unit": "min", "bounds": [10, 20, 40, 60, 120]}),
    ("COZINHAR", "5000010", {"unit": "min", "bounds": [10, 20, 40, 60, 90]}),
    ("LAVAR ROUPA", "5000011", {"unit": "min", "bounds": [10, 20, 40, 60, 90]}),
    ("COMPRAS", "5000012", {"unit": "min", "bounds": [15, 30, 60, 90, 120]}),
    ("DIRIGIR", "5000013", {"unit": "min", "bounds": [15, 30, 60, 90, 120]}),
]

NEW_NAMES = [t[0] for t in TRAINED] + [t[0] for t in LOGGED]


def _ids(conn) -> dict[str, int]:
    return {k: i for i, k in conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()}


def upgrade() -> None:
    conn = op.get_bind()

    # ---- the Artes practice: a root marked for the shop and two leaves ----
    ids = _ids(conn)
    if ARTS_ROOT[0] not in ids:
        conn.execute(sa.text("INSERT INTO attr_nodes (`key`, name, half_life_hours, shop_group) VALUES (:k, :n, NULL, 1)"),
                     {"k": ARTS_ROOT[0], "n": ARTS_ROOT[1]})
        for key, name, _w in ARTS_LEAVES:
            conn.execute(sa.text("INSERT INTO attr_nodes (`key`, name, half_life_hours, shop_group) VALUES (:k, :n, 1440, 0)"),
                         {"k": key, "n": name})
        ids = _ids(conn)
        for key, _name, weight in ARTS_LEAVES:
            conn.execute(sa.text("INSERT INTO attr_edges (parent_id, child_id, weight, is_primary) VALUES (:p, :c, :w, 1)"),
                         {"p": ids[ARTS_ROOT[0]], "c": ids[key], "w": weight})

    # ---- the class numbers the new parents open ----
    for class1, entries in NEW_CLASS2.items():
        for node, code in entries:
            exists = conn.execute(sa.text("SELECT 1 FROM id_class2 WHERE class1_node_id = :c1 AND node_id = :n"),
                                  {"c1": ids[class1], "n": ids[node]}).fetchone()
            if not exists:
                conn.execute(sa.text("INSERT INTO id_class2 (class1_node_id, node_id, code) VALUES (:c1, :n, :c)"),
                             {"c1": ids[class1], "n": ids[node], "c": code})

    # ---- templates and contributions ----
    have = {r[0] for r in conn.execute(sa.text("SELECT action_name FROM action_templates")).fetchall()}
    for name, code, parent, diff, cost, gain, tiers, contribs in TRAINED:
        if name in have:
            continue
        conn.execute(sa.text("""INSERT INTO action_templates
            (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain, tiers, log_only)
            VALUES (:n, :c, :p, 0, :d, :cost, 0, :g, :t, 0)"""),
            {"n": name, "c": code, "p": ids[parent], "d": diff, "cost": cost, "g": gain,
             "t": json.dumps(tiers, ensure_ascii=False)})
        for leaf, weight in contribs.items():
            conn.execute(sa.text("INSERT INTO action_contributions (action_name, leaf_id, weight) VALUES (:n, :l, :w)"),
                         {"n": name, "l": ids[leaf], "w": weight})
    for name, code, tiers in LOGGED:
        if name in have:
            continue
        conn.execute(sa.text("""INSERT INTO action_templates
            (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain, tiers, log_only)
            VALUES (:n, :c, NULL, 0, 0, 0, 0, 0, :t, 1)"""),
            {"n": name, "c": code, "t": json.dumps(tiers, ensure_ascii=False)})


def downgrade() -> None:
    conn = op.get_bind()
    names = {f"n{i}": n for i, n in enumerate(NEW_NAMES)}
    marks = ", ".join(f":{k}" for k in names)
    codes = {f"c{i}": t[1] for i, t in enumerate(TRAINED + LOGGED)}
    code_marks = ", ".join(f":{k}" for k in codes)
    # what profiles bought goes with the catalog entry, as in b9f4: the owned
    # action, its patches (whose ids start with the base's seven digits) and
    # their mark events
    for k, code in codes.items():
        conn.execute(sa.text("DELETE FROM patch_attributes WHERE patch_action_id LIKE :p"), {"p": code + "%"})
        conn.execute(sa.text("DELETE FROM mark_events WHERE action_id LIKE :p OR engine_action_id = :c"),
                     {"p": code + "%", "c": code})
        conn.execute(sa.text("DELETE FROM actions WHERE action_id LIKE :p"), {"p": code + "%"})
    conn.execute(sa.text(f"DELETE FROM user_discoveries WHERE action_name IN ({marks})"), names)
    conn.execute(sa.text(f"DELETE FROM action_contributions WHERE action_name IN ({marks})"), names)
    conn.execute(sa.text(f"DELETE FROM action_templates WHERE code IN ({code_marks})"), codes)

    ids = _ids(conn)
    for class1, entries in NEW_CLASS2.items():
        for node, _code in entries:
            conn.execute(sa.text("DELETE FROM id_class2 WHERE class1_node_id = :c1 AND node_id = :n"),
                         {"c1": ids[class1], "n": ids[node]})

    arts = [ARTS_ROOT[0]] + [k for k, _n, _w in ARTS_LEAVES]
    arts_ids = {f"a{i}": ids[k] for i, k in enumerate(arts) if k in ids}
    if arts_ids:
        conn.execute(sa.text("DELETE FROM rank_claims WHERE node_key IN (:r, :m, :v)"),
                     {"r": arts[0], "m": arts[1], "v": arts[2]})
        am = ", ".join(f":{k}" for k in arts_ids)
        conn.execute(sa.text(f"DELETE FROM user_leaf_scores WHERE leaf_id IN ({am})"), arts_ids)
        conn.execute(sa.text(f"DELETE FROM attr_edges WHERE parent_id IN ({am}) OR child_id IN ({am})"), arts_ids)
        conn.execute(sa.text(f"DELETE FROM attr_nodes WHERE id IN ({am})"), arts_ids)
