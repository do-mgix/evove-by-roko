"""population: diet out, one action per practice, log actions

Revision ID: b9f4c2e7a1d6
Revises: a3c9e5f1b7d2
Create Date: 2026-09-17 12:00:00.000000

The catalog was a test population: a brand per feed, a ball sport per action and
a diet branch. The rule from here on is one question — is this, in practice,
completely different from what is already there, or does it name a part of the
body? Anything finer is a patch the user writes.

- food and diet leave the graph: `nutricao` with its three leaves, the
  `c_alimentacao` practice and the seven actions that fed them. `corpo` loses a
  child worth 0.2 and is reweighted to 0.5/0.3/0.2; `t_saude`, which was mostly
  nutrition, is rebuilt on aerobico, flexibilidade, estabilidade and core;
- five ball sports become ESPORTE, with the athletic profile they shared. The
  anatomically distinct ones stay as they are (CORRIDA, CICLISMO, NATAÇÃO,
  CAMINHADA, ESCALADA);
- leisure is logged, not trained: nine actions become five log actions
  (REDES SOCIAIS, VÍDEO, JOGOS, MÚSICA, GULOSEIMA), marked `log_only`. They feed
  no attribute, so the `c_consumo` practice and its five leaves go with them,
  and their marks stay on the action row. Their ids live in the reserved class
  `5 00 00 ii`: an action with no attribute has no class, so `parent_node_id`
  becomes nullable;
- `mental`'s six equal children summed to 1.0002; they are 0.166667 now, which
  is as close to a sixth as a single-precision weight column gets.

Users keep their logs — the ledger is history — and are refunded the build
points they spent on an action the catalog no longer carries. The rows that
would be left pointing at nothing (the owned action, its patches, its mark
events) are deleted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9f4c2e7a1d6"
down_revision: Union[str, None] = "a3c9e5f1b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DROP_NODES = ("nutricao", "macros", "hidratacao", "estimulantes",
              "c_alimentacao", "c_refeicao", "c_bebida",
              "c_consumo", "c_redes", "c_video", "c_jogos", "c_audio", "c_indulgencia")

DROP_ACTIONS = ("WATER", "COFFEE", "TEA", "BREAKFAST", "LUNCH", "DINNER", "SNACK",
                "FUTEBOL", "BASQUETE", "VÔLEI", "TÊNIS", "SURF",
                "INSTAGRAM", "TIKTOK", "TWITTER", "YOUTUBE", "WATCH FILM",
                "WATCH SERIES", "VIDEO GAMES", "MUSIC", "GULOSEIMA")

# parent -> {child: weight}; every child link a parent keeps, so the weights sum to 1
REWEIGHT = {
    "corpo": {"musculatura": 0.5, "cardiovascular": 0.3, "mobilidade": 0.2},
    "t_saude": {"aerobico": 0.5, "flexibilidade": 0.2, "estabilidade": 0.15, "core": 0.15},
    # six equal children that summed to 1.0002; weight is a single-precision
    # column, so six sevens is as exact as it gets here
    "mental": {k: 0.166667 for k in ("t_aprendizado", "t_memoria", "t_foco",
                                     "t_linguagem", "t_coordenacao", "t_emocao")},
}

ESPORTE = {"action": "ESPORTE", "code": "5020107", "parent": "aerobico", "type": 0, "diff": 3,
           "cost": 8, "token_cost": 0, "token_gain": 25,
           "tiers": '{"unit": "min", "bounds": [15, 30, 60, 90, 120]}'}

# the athletic profile the five shared: cardio, the coordination a game asks for,
# and the legs and core under it
ESPORTE_CONTRIBS = {"aerobico": 0.25, "anaerobico": 0.2, "coordenacao": 0.2, "equilibrio": 0.1,
                    "quadriceps": 0.1, "core": 0.1, "panturrilha": 0.05, "c_esportes": 1.0}

LOG_ACTIONS = [
    ("REDES SOCIAIS", "5000001", 12, '{"unit": "min", "bounds": [10, 30, 60, 120, 180]}'),
    ("VÍDEO", "5000002", 12, '{"unit": "min", "bounds": [20, 45, 90, 150, 240]}'),
    ("JOGOS", "5000003", 20, '{"unit": "min", "bounds": [15, 30, 60, 120, 180]}'),
    ("MÚSICA", "5000004", 0, '{"unit": "min", "bounds": [15, 30, 60, 120, 180]}'),
    ("GULOSEIMA", "5000005", 10, '{"unit": "porções", "bounds": [1, 2, 3, 4, 5]}'),
]


def _in(sql: str, name: str) -> sa.TextClause:
    """A text() with an IN list; SQLAlchemy needs the bind marked expanding."""
    return sa.text(sql).bindparams(sa.bindparam(name, expanding=True))


def _node_ids(conn) -> dict[str, int]:
    return {k: i for i, k in conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()}


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("action_templates",
                  sa.Column("log_only", sa.Boolean(), nullable=False, server_default=sa.false()))
    # a log action is registered under no attribute, and that is what its id says
    op.alter_column("action_templates", "parent_node_id",
                    existing_type=sa.BigInteger(), nullable=True)

    # ---- owned actions of a catalog entry that is going away ----
    gone = {"names": list(DROP_ACTIONS)}
    owned = conn.execute(_in("""
        SELECT a.user_id, a.action_id, COALESCE(t.cost, 0)
        FROM actions a LEFT JOIN action_templates t ON t.action_name = a.name
        WHERE a.name IN :names""", "names"), gone).fetchall()
    for user_id, action_id, cost in owned:
        ids = {"u": user_id, "a": action_id, "pre": action_id + "%"}
        conn.execute(sa.text("""DELETE FROM patch_attributes
            WHERE user_id = :u AND patch_action_id LIKE :pre"""), ids)
        conn.execute(sa.text("""DELETE FROM mark_events
            WHERE user_id = :u AND (engine_action_id = :a OR action_id LIKE :pre)"""), ids)
        conn.execute(sa.text("""DELETE FROM actions
            WHERE user_id = :u AND (action_id = :a OR base_action_id = :a)"""), ids)
        if cost:
            conn.execute(sa.text("""UPDATE user_state SET build_points = build_points + :c
                WHERE user_id = :u"""), {"c": int(cost), "u": user_id})

    conn.execute(_in("DELETE FROM action_contributions WHERE action_name IN :names", "names"), gone)
    conn.execute(_in("DELETE FROM action_templates WHERE action_name IN :names", "names"), gone)

    # ---- the attributes nothing feeds any more ----
    # attr_nodes cascades to attr_edges, action_contributions, user_leaf_scores
    # and the class registries
    conn.execute(_in("DELETE FROM attr_nodes WHERE `key` IN :keys", "keys"),
                 {"keys": list(DROP_NODES)})

    # ---- weights ----
    ids = _node_ids(conn)
    for parent, children in REWEIGHT.items():
        for child, weight in children.items():
            conn.execute(sa.text("""UPDATE attr_edges SET weight = :w
                WHERE parent_id = :p AND child_id = :c"""),
                         {"w": float(weight), "p": ids[parent], "c": ids[child]})
    # t_saude drew on nutrition for half its weight; what is left is a different set
    for child, weight in REWEIGHT["t_saude"].items():
        exists = conn.execute(sa.text("""SELECT 1 FROM attr_edges
            WHERE parent_id = :p AND child_id = :c"""),
                              {"p": ids["t_saude"], "c": ids[child]}).fetchone()
        if not exists:
            conn.execute(sa.text("""INSERT INTO attr_edges (parent_id, child_id, weight, is_primary)
                VALUES (:p, :c, :w, 0)"""),
                         {"p": ids["t_saude"], "c": ids[child], "w": float(weight)})

    # ---- ESPORTE ----
    # 5020107, not the 01 and 05 the ball sports leave free: a reused code would
    # inherit their mark events
    conn.execute(sa.text("""INSERT INTO action_templates
        (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain, tiers, log_only)
        VALUES (:n, :c, :p, :ty, :d, :co, :tc, :tg, :j, 0)"""),
                 {"n": ESPORTE["action"], "c": ESPORTE["code"], "p": ids[ESPORTE["parent"]],
                  "ty": ESPORTE["type"], "d": ESPORTE["diff"], "co": ESPORTE["cost"],
                  "tc": ESPORTE["token_cost"], "tg": ESPORTE["token_gain"], "j": ESPORTE["tiers"]})
    for leaf, weight in ESPORTE_CONTRIBS.items():
        conn.execute(sa.text("""INSERT INTO action_contributions (action_name, leaf_id, weight)
            VALUES (:n, :l, :w)"""),
                     {"n": ESPORTE["action"], "l": ids[leaf], "w": float(weight)})

    # ---- log actions ----
    for name, code, token_cost, tiers in LOG_ACTIONS:
        conn.execute(sa.text("""INSERT INTO action_templates
            (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain, tiers, log_only)
            VALUES (:n, :c, NULL, 0, 0, 0, :tc, 0, :j, 1)"""),
                     {"n": name, "c": code, "tc": token_cost, "j": tiers})


def downgrade() -> None:
    """Restores the shape, not the population: the attributes and actions this
    revision removed are in `seeds/attributes_tree.engine.json` and would come
    back without the marks and ids their users had."""
    conn = op.get_bind()

    names = [a[0] for a in LOG_ACTIONS] + [ESPORTE["action"]]
    conn.execute(_in("DELETE FROM action_contributions WHERE action_name IN :names", "names"),
                 {"names": names})
    conn.execute(_in("DELETE FROM actions WHERE name IN :names", "names"), {"names": names})
    conn.execute(_in("DELETE FROM action_templates WHERE action_name IN :names", "names"),
                 {"names": names})

    conn.execute(sa.text("UPDATE action_templates SET parent_node_id = ("
                         "SELECT id FROM attr_nodes WHERE `key` = 'foco') "
                         "WHERE parent_node_id IS NULL"))
    op.alter_column("action_templates", "parent_node_id",
                    existing_type=sa.BigInteger(), nullable=False)
    op.drop_column("action_templates", "log_only")
