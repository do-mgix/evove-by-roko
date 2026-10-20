"""shop discovery, authors, nicknames, passcodes and allies

Revision ID: d9b1c3e5f7a9
Revises: c7e9a1b3d5f7
Create Date: 2026-10-20 12:00:00.000000

The catalog is hidden until discovered: every profile starts having discovered
the actions it already owns. Every catalog action has an author; all of them so
far are roko's. Every profile gets a random nickname and a passcode, by which
another profile can add it as an ally.
"""
import random
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.domain.names import unique_nickname, unique_passcode


revision: str = "d9b1c3e5f7a9"
down_revision: Union[str, None] = "c7e9a1b3d5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("action_templates", sa.Column("author", sa.String(32), nullable=False, server_default="roko"))
    op.create_table(
        "user_discoveries",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("action_name", sa.String(128), primary_key=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
    )
    op.add_column("user_state", sa.Column("discover_date", sa.Date(), nullable=True))
    op.add_column("user_state", sa.Column("discover_used", sa.Integer(), nullable=False, server_default="0"))
    op.execute("""INSERT INTO user_discoveries (user_id, action_name, discovered_at)
        SELECT DISTINCT a.user_id, t.action_name, NOW()
        FROM actions a JOIN action_templates t ON t.action_name = UPPER(a.name)
        WHERE a.deleted = 0""")

    op.add_column("users", sa.Column("nickname", sa.String(24), nullable=True))
    op.add_column("users", sa.Column("passcode", sa.String(8), nullable=True))
    conn = op.get_bind()
    rng = random.Random()
    names: set[str] = set()
    codes: set[str] = set()
    for (user_id,) in conn.execute(sa.text("SELECT id FROM users ORDER BY id")).all():
        nick = unique_nickname(rng, names)
        code = unique_passcode(rng, codes)
        names.add(nick)
        codes.add(code)
        conn.execute(sa.text("UPDATE users SET nickname = :n, passcode = :c WHERE id = :i"),
                     {"n": nick, "c": code, "i": user_id})
    op.create_unique_constraint("uq_users_nickname", "users", ["nickname"])
    op.create_unique_constraint("uq_users_passcode", "users", ["passcode"])

    op.create_table(
        "allies",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ally_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("allies")
    op.drop_constraint("uq_users_passcode", "users", type_="unique")
    op.drop_constraint("uq_users_nickname", "users", type_="unique")
    op.drop_column("users", "passcode")
    op.drop_column("users", "nickname")
    op.drop_column("user_state", "discover_used")
    op.drop_column("user_state", "discover_date")
    op.drop_table("user_discoveries")
    op.drop_column("action_templates", "author")
