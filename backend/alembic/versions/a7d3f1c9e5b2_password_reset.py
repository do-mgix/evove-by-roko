"""password recovery by e-mail

Revision ID: a7d3f1c9e5b2
Revises: c1a7e4b9d2f6
Create Date: 2026-09-26 18:00:00.000000

A profile may now carry an e-mail address, used only to send a link that sets a
new password. The links live in password_resets, stored as a SHA-256 digest like
the session tokens, and die with the profile.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7d3f1c9e5b2"
down_revision: Union[str, None] = "c1a7e4b9d2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(254), nullable=True))
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    op.create_table(
        "password_resets",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("password_resets")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email")
