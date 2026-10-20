"""economy: scarce tokens, abundant points, an hp of 25, Greek ranks

Revision ID: a2f4c6e8b1d3
Revises: e4b9d2f7a3c1
Create Date: 2026-10-20 09:00:00.000000

Tokens go to a cap of 25 and acts release 1 to 4 of them: every template and
every bought action has its token gain and cost divided by seven, rounded, the
gain kept within 1-4. Build points become points, a hundred times as many: the
shop's prices and every balance are multiplied by 100. The journey's energy is
an hp of 25 now, so what was left of 1000 is scaled down to it.

The ranks are the 24 Greek letters, α to ω. Nobody stands past the 24th rank, so
only the cap is enforced.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a2f4c6e8b1d3"
down_revision: Union[str, None] = "e4b9d2f7a3c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("action_templates", "actions"):
        op.execute(f"""UPDATE {table} SET
            token_gain = CASE WHEN token_gain > 0 THEN LEAST(4, GREATEST(1, ROUND(token_gain / 7))) ELSE 0 END,
            token_cost = CASE WHEN token_cost > 0 THEN GREATEST(1, ROUND(token_cost / 7)) ELSE 0 END""")
    op.execute("UPDATE action_templates SET cost = cost * 100")
    op.execute("""UPDATE user_state SET
        max_tokens = 25,
        tokens = LEAST(tokens, 25),
        build_points = build_points * 100,
        energy = LEAST(25, GREATEST(1, CEIL(energy / 40)))""")
    op.execute("ALTER TABLE user_state ALTER COLUMN energy SET DEFAULT 25")
    op.execute("ALTER TABLE user_state ALTER COLUMN max_tokens SET DEFAULT 25")
    op.execute("UPDATE user_leaf_scores SET rank_index = 23 WHERE rank_index > 23")
    op.execute("UPDATE user_attributes SET rank_index = 23 WHERE rank_index > 23")


def downgrade() -> None:
    op.execute("""UPDATE user_state SET
        max_tokens = 100,
        build_points = FLOOR(build_points / 100),
        energy = LEAST(1000, energy * 40)""")
    op.execute("UPDATE action_templates SET cost = FLOOR(cost / 100)")
    for table in ("action_templates", "actions"):
        op.execute(f"UPDATE {table} SET token_gain = token_gain * 7, token_cost = token_cost * 7")
    op.execute("ALTER TABLE user_state ALTER COLUMN energy SET DEFAULT 1000")
    op.execute("ALTER TABLE user_state ALTER COLUMN max_tokens SET DEFAULT 100")
