"""patch link weights

Revision ID: a3c9e5f1b7d2
Revises: f3b8d1e7a4c2
Create Date: 2026-09-15 12:00:00.000000

A patch trained every attribute it links with all of an act's marks. Each link
now carries a weight, the share of those marks its attribute receives. Every
existing link starts at 1, so no patch pays differently than it did.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3c9e5f1b7d2"
down_revision: Union[str, None] = "f3b8d1e7a4c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patch_attributes", sa.Column("weight", sa.Float(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("patch_attributes", "weight")
