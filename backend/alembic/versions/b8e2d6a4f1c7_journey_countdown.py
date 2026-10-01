"""journey mode: a countdown to the next checkpoint

Revision ID: b8e2d6a4f1c7
Revises: a7d3f1c9e5b2
Create Date: 2026-09-29 10:00:00.000000

The stage map of 19+n-day stages, counted down once a day, becomes a clock:
stages of 1, 3, 7, 14, 30 and 60 days, then doubling, each cut into smaller
points (src.domain.journey). A stage is now timed from the moment it began.

Every profile starts the new journey at stage 1, now, with a full tank. Skill
and build points already earned stay.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e2d6a4f1c7"
down_revision: Union[str, None] = "a7d3f1c9e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_state", sa.Column("journey_started_at", sa.DateTime(), nullable=True))
    op.add_column("user_state", sa.Column("journey_points", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_state", sa.Column("journey_resets", sa.Integer(), nullable=False, server_default="0"))
    # journey_started_at stays NULL: the backend starts the clock on the next
    # load, in its own time zone, which the database's NOW() may not share
    op.execute("UPDATE user_state SET stage = 1, energy = 1000")
    op.drop_column("user_state", "days_until_next_checkpoint")
    op.drop_column("user_state", "last_checkpoint_check")


def downgrade() -> None:
    op.add_column("user_state", sa.Column("last_checkpoint_check", sa.Date(), nullable=True))
    op.add_column("user_state", sa.Column("days_until_next_checkpoint", sa.Integer(), nullable=False, server_default="20"))
    op.drop_column("user_state", "journey_resets")
    op.drop_column("user_state", "journey_points")
    op.drop_column("user_state", "journey_started_at")
