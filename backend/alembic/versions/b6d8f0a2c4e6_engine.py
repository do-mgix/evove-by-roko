"""the engine: every profile's evove as a state of its own

Revision ID: b6d8f0a2c4e6
Revises: a4c6e8f0b2d4
Create Date: 2026-10-23 10:00:00.000000

The app becomes an engine that draws whatever modules the server says a profile
has (src.domain.engine). `user_engine` keeps, per profile, that state as JSON —
modules, the story's step, counters, the selector, the entities met — and a
passcode of eight characters that hands the build to another profile.

Every profile that exists already is given the legacy state: all its modules,
the story told, roko met. New profiles start from agir alone.
"""
import json
import random
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6d8f0a2c4e6"
down_revision: Union[str, None] = "a4c6e8f0b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MODULES = ["act", "shop", "roko", "agenda", "attributes", "journey", "build"]


def upgrade() -> None:
    op.create_table(
        "user_engine",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("passcode", sa.String(8), nullable=False, unique=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    conn = op.get_bind()
    rng = random.SystemRandom()
    taken: set[str] = set()
    now = datetime.now().replace(microsecond=0)
    for (user_id,) in conn.execute(sa.text("SELECT id FROM users")).fetchall():
        code = "".join(rng.choice(ALPHABET) for _ in range(8))
        while code in taken:
            code = "".join(rng.choice(ALPHABET) for _ in range(8))
        taken.add(code)
        state = {
            "v": 1, "modules": MODULES, "fresh": [], "story": "done", "entities": ["roko"], "selector": 1,
            "counters": {}, "session": {"n": 0, "at": None, "seed": rng.randrange(1 << 30)}, "ghosts": [], "line": None,
        }
        conn.execute(sa.text("INSERT INTO user_engine (user_id, passcode, state, updated_at) VALUES (:u, :p, :s, :t)"),
                     {"u": user_id, "p": code, "s": json.dumps(state), "t": now})


def downgrade() -> None:
    op.drop_table("user_engine")
