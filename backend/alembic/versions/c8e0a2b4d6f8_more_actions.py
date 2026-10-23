"""more actions: twenty-one more of what a day can hold

Revision ID: c8e0a2b4d6f8
Revises: b6d8f0a2c4e6
Create Date: 2026-10-23 11:00:00.000000

The engine's story starts by offering actions the profile does not own, so the
catalog is what it draws from, and a wider one gives every new profile a
different start. Twenty-one actions, under the same rule as f2c8: each one
atomic and generic, with anything finer left to a patch (TRILHA · SERRA,
LUTA · JUDÔ, IDIOMA · INGLÊS).

- the body: POLICHINELO, REMO and TRILHA under Aeróbico, LUTA under Coordenação
  (a sport, filed with ESPORTE), PILATES under Core, PARADA DE MÃO under
  Deltoide, SALTO under Quadríceps;
- the mind: IDIOMA and MEMORIZAÇÃO under Hipocampo, CÁLCULO under Função
  Executiva, VISUALIZAÇÃO under Visual, a meditation;
- language and the arts: APRESENTAÇÃO and POESIA under Broca, FOTOGRAFIA under
  Visual, COMPOR under Auditivo, ARTESANATO under Somatossensorial, which opens
  class `07 03`;
- four log actions, the day's ledger: BANHO, REFEIÇÃO and COCHILO neutral,
  NOTÍCIAS a consumption that spends a token.

No new attribute: every leaf they feed already exists. Codes continue after the
last position of each class, never into one an older action held.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e0a2b4d6f8"
down_revision: Union[str, None] = "b6d8f0a2c4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CLASS2 = {"sensorial": [("somatossensorial", "03")]}

# name, code, parent, diff, cost, token_gain, tiers, {leaf: weight}
TRAINED = [
    ("POLICHINELO", "5020110", "aerobico", 1, 300, 1, {"unit": "reps", "bounds": [20, 50, 100, 200, 300]},
     {"aerobico": 0.5, "coordenacao": 0.2, "panturrilha": 0.15, "deltoide": 0.15, "c_cardio": 1.0}),
    ("REMO", "5020111", "aerobico", 3, 800, 3, {"unit": "min", "bounds": [5, 10, 20, 30, 45]},
     {"aerobico": 0.45, "dorsal": 0.25, "quadriceps": 0.15, "biceps": 0.15, "c_cardio": 1.0}),
    ("TRILHA", "5020112", "aerobico", 3, 800, 3, {"unit": "min", "bounds": [30, 60, 120, 180, 240]},
     {"aerobico": 0.4, "quadriceps": 0.2, "panturrilha": 0.15, "equilibrio": 0.15, "gluteo": 0.1, "c_cardio": 1.0}),
    ("LUTA", "5090202", "coordenacao", 3, 800, 4, {"unit": "min", "bounds": [10, 20, 40, 60, 90]},
     {"coordenacao": 0.25, "anaerobico": 0.25, "aerobico": 0.2, "core": 0.15, "equilibrio": 0.15, "c_esportes": 1.0}),
    ("PILATES", "5010503", "core", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 30, 45, 60]},
     {"core": 0.4, "estabilidade": 0.25, "flexibilidade": 0.2, "equilibrio": 0.15, "c_mobilidade": 1.0}),
    ("PARADA DE MÃO", "5010103", "deltoide", 3, 800, 3, {"unit": "s", "bounds": [5, 15, 30, 60, 120]},
     {"deltoide": 0.3, "equilibrio": 0.3, "triceps": 0.2, "core": 0.2, "c_calistenia": 1.0}),
    ("SALTO", "5010604", "quadriceps", 2, 500, 2, {"unit": "reps", "bounds": [10, 25, 50, 80, 120]},
     {"quadriceps": 0.35, "panturrilha": 0.25, "gluteo": 0.2, "anaerobico": 0.2, "c_calistenia": 1.0}),
    ("IDIOMA", "5060102", "hipocampo", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 120]},
     {"hipocampo": 0.35, "wernicke": 0.35, "broca": 0.3, "c_leitura": 1.0}),
    ("MEMORIZAÇÃO", "5060103", "hipocampo", 1, 300, 1, {"unit": "min", "bounds": [5, 10, 20, 30, 60]},
     {"hipocampo": 0.6, "foco": 0.25, "executiva": 0.15, "c_raciocinio": 1.0}),
    ("CÁLCULO", "5050212", "executiva", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 90]},
     {"executiva": 0.45, "foco": 0.3, "hipocampo": 0.25, "c_raciocinio": 1.0}),
    ("VISUALIZAÇÃO", "5070108", "visual", 1, 300, 1, {"unit": "min", "bounds": [3, 5, 10, 20, 30]},
     {"visual": 0.4, "foco": 0.3, "amigdala": 0.3, "c_meditacao": 1.0}),
    ("FOTOGRAFIA", "5070109", "visual", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 120]},
     {"visual": 0.55, "foco": 0.2, "recompensa": 0.15, "coordenacao": 0.1, "c_artes_visuais": 1.0}),
    ("APRESENTAÇÃO", "5080106", "broca", 3, 800, 3, {"unit": "min", "bounds": [3, 5, 10, 20, 40]},
     {"broca": 0.4, "amigdala": 0.25, "executiva": 0.2, "wernicke": 0.15, "c_argumentacao": 1.0}),
    ("POESIA", "5080107", "broca", 2, 500, 2, {"unit": "linhas", "bounds": [4, 8, 14, 30, 60]},
     {"broca": 0.45, "auditivo": 0.2, "recompensa": 0.2, "visual": 0.15, "c_narrativa": 1.0}),
    ("COMPOR", "5070205", "auditivo", 3, 800, 3, {"unit": "min", "bounds": [10, 20, 40, 60, 120]},
     {"auditivo": 0.4, "executiva": 0.2, "recompensa": 0.2, "hipocampo": 0.2, "c_musica": 1.0}),
    ("ARTESANATO", "5070301", "somatossensorial", 2, 500, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 120]},
     {"somatossensorial": 0.35, "coordenacao": 0.3, "visual": 0.2, "foco": 0.15, "c_artes_visuais": 1.0}),
]

# name, code, token_cost, tiers — log actions: no parent, no contributions
LOGGED = [
    ("BANHO", "5000014", 0, {"unit": "min", "bounds": [3, 5, 10, 15, 25]}),
    ("REFEIÇÃO", "5000015", 0, {"unit": "min", "bounds": [5, 10, 20, 30, 60]}),
    ("COCHILO", "5000016", 0, {"unit": "min", "bounds": [10, 20, 30, 60, 90]}),
    ("NOTÍCIAS", "5000017", 1, {"unit": "min", "bounds": [5, 10, 20, 30, 60]}),
]

NEW_NAMES = [t[0] for t in TRAINED] + [t[0] for t in LOGGED]


def _ids(conn) -> dict[str, int]:
    return {k: i for i, k in conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()}


def upgrade() -> None:
    conn = op.get_bind()
    ids = _ids(conn)
    for class1, entries in NEW_CLASS2.items():
        for node, code in entries:
            exists = conn.execute(sa.text("SELECT 1 FROM id_class2 WHERE class1_node_id = :c1 AND node_id = :n"),
                                  {"c1": ids[class1], "n": ids[node]}).fetchone()
            if not exists:
                conn.execute(sa.text("INSERT INTO id_class2 (class1_node_id, node_id, code) VALUES (:c1, :n, :c)"),
                             {"c1": ids[class1], "n": ids[node], "c": code})

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
    for name, code, token_cost, tiers in LOGGED:
        if name in have:
            continue
        conn.execute(sa.text("""INSERT INTO action_templates
            (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain, tiers, log_only)
            VALUES (:n, :c, NULL, 0, 0, 0, :tc, 0, :t, 1)"""),
            {"n": name, "c": code, "tc": token_cost, "t": json.dumps(tiers, ensure_ascii=False)})


def downgrade() -> None:
    conn = op.get_bind()
    names = {f"n{i}": n for i, n in enumerate(NEW_NAMES)}
    marks = ", ".join(f":{k}" for k in names)
    codes = {f"c{i}": t[1] for i, t in enumerate(TRAINED + LOGGED)}
    code_marks = ", ".join(f":{k}" for k in codes)
    for code in codes.values():
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
