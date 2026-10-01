"""log actions: ônibus and trabalho

Revision ID: c3f8a1d6e9b4
Revises: b8e2d6a4f1c7
Create Date: 2026-10-01 10:00:00.000000

Two things a day is made of that the catalog could not log: the bus ride and
work, taken generically. Both are log actions — registered under no attribute,
feeding none — and neutral like MÚSICA: they neither cost nor release tokens.
The line, the job or what was playing goes in the act's note.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f8a1d6e9b4"
down_revision: Union[str, None] = "b8e2d6a4f1c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW = [
    ("ÔNIBUS", "5000006", '{"unit": "min", "bounds": [15, 30, 60, 90, 120]}'),
    ("TRABALHO", "5000007", '{"unit": "h", "bounds": [1, 2, 4, 6, 8]}'),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, code, tiers in NEW:
        exists = conn.execute(sa.text("SELECT 1 FROM action_templates WHERE action_name = :n"),
                              {"n": name}).fetchone()
        if exists:
            continue
        conn.execute(sa.text("""INSERT INTO action_templates
            (action_name, code, parent_node_id, type, diff, cost, token_cost, token_gain, tiers, log_only)
            VALUES (:n, :c, NULL, 0, 0, 0, 0, 0, :t, 1)"""), {"n": name, "c": code, "t": tiers})


def downgrade() -> None:
    conn = op.get_bind()
    for name, _code, _tiers in NEW:
        conn.execute(sa.text("DELETE FROM action_templates WHERE action_name = :n"), {"n": name})
