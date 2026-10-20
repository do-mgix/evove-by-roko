"""agenda: to-dos, projects that keep time and become emblems, thoughts

Revision ID: c7e9a1b3d5f7
Revises: b5d7e9f1a3c5
Create Date: 2026-10-20 11:00:00.000000

A to-do is a list of actions, closed by hand, optionally inside a project and
with a deadline. A project counts the time it spends active and ends either
completed or finished, which is what turns it into an emblem. A thought is a few
words on a log, or on the whole day when `log_id` is empty.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e9a1b3d5f7"
down_revision: Union[str, None] = "b5d7e9f1a3c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("active_seconds", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("active_since", sa.DateTime(), nullable=True))
    op.add_column("projects", sa.Column("outcome", sa.String(12), nullable=True))
    op.add_column("projects", sa.Column("ended_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE projects SET active_since = NOW() WHERE active = 1")
    op.create_table(
        "todos",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("project_pk", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("done_at", sa.DateTime(), nullable=True),
        sa.Column("reward", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "todo_actions",
        sa.Column("todo_id", sa.BigInteger(), sa.ForeignKey("todos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("action_id", sa.String(16), primary_key=True),
    )
    op.create_table(
        "thoughts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("log_id", sa.BigInteger(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_thoughts_user_day", "thoughts", ["user_id", "day"])


def downgrade() -> None:
    op.drop_index("ix_thoughts_user_day", table_name="thoughts")
    op.drop_table("thoughts")
    op.drop_table("todo_actions")
    op.drop_table("todos")
    for col in ("ended_at", "outcome", "active_since", "active_seconds"):
        op.drop_column("projects", col)
