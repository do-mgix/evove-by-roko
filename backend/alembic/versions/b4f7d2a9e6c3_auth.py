"""passwords and sessions

Revision ID: b4f7d2a9e6c3
Revises: a1e5c9b3d7f2
Create Date: 2026-09-10 09:30:00.000000

Identity was a plaintext X-Evove-Username header: anyone could act as anyone by
editing one request. Profiles now carry a bcrypt hash and the API is reached
with a session token.

Existing profiles are dropped rather than migrated — they have no password and
there is no safe way to invent one. Register again through /auth/register.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4f7d2a9e6c3"
down_revision: Union[str, None] = "a1e5c9b3d7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clear first: password_hash is NOT NULL and passwordless rows cannot satisfy
    # it. Every other user table cascades from users.
    op.execute("DELETE FROM users")

    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=False))

    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_column("users", "password_hash")
