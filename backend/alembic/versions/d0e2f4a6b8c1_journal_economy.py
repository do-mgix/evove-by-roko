"""journal economy: tokens priced after the plain-text ledger

Revision ID: d0e2f4a6b8c1
Revises: c8e0a2b4d6f8
Create Date: 2026-10-28 09:00:00.000000

The ledger kept by hand in ~/journal/token-history, from September on, moves
tokens in steps of five on a stock of 100: work, a project, the course or
applying for jobs +10, writing +10 to +20, cooking +20, a chore +5 to +10;
music -5, light reading -5, an episode -15, a film -10 to -20, an evening of
videos -15 to -30, a game -30. One token here is five of those, so the stock of
25 holds a little more than the ledger's 100, which ran into its cap on one day
in five and threw the rest away.

The trained actions already release about that (projeto +10 is FEATURE (AI)'s
2), so only the ledger is brought in:

- work and chores stop being neutral: TRABALHO +2, COZINHAR +3, LIMPEZA and
  LAVAR ROUPA +1. They stay log actions — no attribute — that release tokens;
- leisure is priced by its tier, the six amounts in `tiers.cost`
  (src.domain.marks): MÚSICA 1 to 2, VÍDEO 1 to 6, JOGOS 2 to 8, REDES SOCIAIS
  1 to 4. The flat `token_cost` keeps the usual tier's price, for the shop;
- four log actions the ledger names and the catalog lacked: SÉRIE by episodes,
  FILME by length, LEITURA (reading for leisure: comics, manga, novels — READ
  stays the trained one) and VAGAS, applying for jobs, +2.

Every profile that already logs leisure (owns JOGOS or VÍDEO) is handed SÉRIE,
FILME and LEITURA, which split what it logged as one of those; VAGAS is only
discovered, by whoever owns TRABALHO, and waits in the shop at no price. Owned
actions and their patches take the new values too, since an action keeps the
token amounts it was bought with.
"""
import json
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e2f4a6b8c1"
down_revision: Union[str, None] = "c8e0a2b4d6f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# name: (token_cost, token_gain, tier prices or None) — the actions already there
REPRICED = {
    "TRABALHO": (0, 2, None),
    "COZINHAR": (0, 3, None),
    "LIMPEZA": (0, 1, None),
    "LAVAR ROUPA": (0, 1, None),
    "MÚSICA": (1, 0, [1, 1, 1, 1, 2, 2]),
    "VÍDEO": (3, 0, [1, 2, 3, 4, 6, 6]),
    "JOGOS": (4, 0, [2, 3, 4, 6, 6, 8]),
    "REDES SOCIAIS": (2, 0, [1, 1, 2, 3, 4, 4]),
}

# what they were, for the downgrade
BEFORE = {
    "TRABALHO": (0, 0), "COZINHAR": (0, 0), "LIMPEZA": (0, 0), "LAVAR ROUPA": (0, 0),
    "MÚSICA": (0, 0), "VÍDEO": (2, 0), "JOGOS": (3, 0), "REDES SOCIAIS": (2, 0),
}

# name, code, token_cost, token_gain, tiers — new log actions
LOGGED = [
    ("SÉRIE", "5000018", 3, 0, {"unit": "ep", "bounds": [1, 2, 3, 4, 6],
                                "labels": ["<1 ep", "1 ep", "2 ep", "3 ep", "4–5 ep", "6+ ep"],
                                "cost": [1, 3, 6, 9, 12, 18]}),
    ("FILME", "5000019", 3, 0, {"unit": "min", "bounds": [30, 60, 90, 120, 150], "cost": [1, 2, 3, 3, 4, 4]}),
    ("LEITURA", "5000020", 1, 0, {"unit": "min", "bounds": [10, 20, 40, 60, 120], "cost": [1, 1, 1, 1, 2, 2]}),
    ("VAGAS", "5000021", 0, 2, {"unit": "min", "bounds": [10, 20, 40, 60, 120]}),
]

HANDED = ("SÉRIE", "FILME", "LEITURA")
LEISURE_CODES = ("5000002", "5000003")   # VÍDEO, JOGOS
WORK_CODE = "5000007"                    # TRABALHO


def _tiers(conn, name: str) -> dict:
    raw = conn.execute(sa.text("SELECT tiers FROM action_templates WHERE action_name = :n"), {"n": name}).scalar()
    if isinstance(raw, (bytes, str)):
        raw = json.loads(raw)
    return dict(raw or {})


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now().replace(microsecond=0)

    for name, (cost, gain, prices) in REPRICED.items():
        tiers = _tiers(conn, name)
        if prices:
            tiers["cost"] = prices
        conn.execute(sa.text("""UPDATE action_templates SET token_cost = :c, token_gain = :g, tiers = :t
                                WHERE action_name = :n"""),
                     {"c": cost, "g": gain, "t": json.dumps(tiers, ensure_ascii=False), "n": name})
        code = conn.execute(sa.text("SELECT code FROM action_templates WHERE action_name = :n"), {"n": name}).scalar()
        conn.execute(sa.text("""UPDATE actions SET token_cost = :c, token_gain = :g
                                WHERE action_id = :code OR base_action_id = :code"""),
                     {"c": cost, "g": gain, "code": code})

    have = {r[0] for r in conn.execute(sa.text("SELECT action_name FROM action_templates")).fetchall()}
    for name, code, cost, gain, tiers in LOGGED:
        if name in have:
            continue
        conn.execute(sa.text("""INSERT INTO action_templates
            (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain, tiers, log_only)
            VALUES (:n, :c, NULL, 0, 0, 0, :tc, :tg, :t, 1)"""),
            {"n": name, "c": code, "tc": cost, "tg": gain, "t": json.dumps(tiers, ensure_ascii=False)})

    leisure = [r[0] for r in conn.execute(sa.text(
        "SELECT DISTINCT user_id FROM actions WHERE deleted = 0 AND action_id IN :codes"
    ).bindparams(sa.bindparam("codes", expanding=True)), {"codes": list(LEISURE_CODES)}).fetchall()]
    workers = [r[0] for r in conn.execute(sa.text(
        "SELECT DISTINCT user_id FROM actions WHERE deleted = 0 AND action_id = :c"), {"c": WORK_CODE}).fetchall()]
    by_name = {t[0]: t for t in LOGGED}

    def discover(user_id: int, name: str) -> None:
        conn.execute(sa.text("""INSERT IGNORE INTO user_discoveries (user_id, action_name, discovered_at)
                                VALUES (:u, :n, :at)"""), {"u": user_id, "n": name, "at": now})

    for user_id in leisure:
        for name in HANDED:
            _n, code, cost, gain, _t = by_name[name]
            owned = conn.execute(sa.text("SELECT 1 FROM actions WHERE user_id = :u AND action_id = :c"),
                                 {"u": user_id, "c": code}).fetchone()
            if not owned:
                conn.execute(sa.text("""INSERT INTO actions
                    (user_id, action_id, name, type, diff, value, max_value, score, deleted, token_cost, token_gain)
                    VALUES (:u, :c, :n, 0, 0, 0, 0, 0, 0, :tc, :tg)"""),
                    {"u": user_id, "c": code, "n": name, "tc": cost, "tg": gain})
            discover(user_id, name)
    for user_id in workers:
        discover(user_id, "VAGAS")


def downgrade() -> None:
    conn = op.get_bind()
    codes = {f"c{i}": t[1] for i, t in enumerate(LOGGED)}
    names = {f"n{i}": t[0] for i, t in enumerate(LOGGED)}
    code_marks = ", ".join(f":{k}" for k in codes)
    name_marks = ", ".join(f":{k}" for k in names)
    for code in codes.values():
        conn.execute(sa.text("DELETE FROM mark_events WHERE action_id LIKE :p OR engine_action_id = :c"),
                     {"p": code + "%", "c": code})
        conn.execute(sa.text("DELETE FROM actions WHERE action_id LIKE :p"), {"p": code + "%"})
    conn.execute(sa.text(f"DELETE FROM user_discoveries WHERE action_name IN ({name_marks})"), names)
    conn.execute(sa.text(f"DELETE FROM action_templates WHERE code IN ({code_marks})"), codes)

    for name, (cost, gain) in BEFORE.items():
        tiers = _tiers(conn, name)
        tiers.pop("cost", None)
        conn.execute(sa.text("""UPDATE action_templates SET token_cost = :c, token_gain = :g, tiers = :t
                                WHERE action_name = :n"""),
                     {"c": cost, "g": gain, "t": json.dumps(tiers, ensure_ascii=False), "n": name})
        code = conn.execute(sa.text("SELECT code FROM action_templates WHERE action_name = :n"), {"n": name}).scalar()
        conn.execute(sa.text("""UPDATE actions SET token_cost = :c, token_gain = :g
                                WHERE action_id = :code OR base_action_id = :code"""),
                     {"c": cost, "g": gain, "code": code})
