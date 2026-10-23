"""log undo: what an act changed, kept on its log

Revision ID: a4c6e8f0b2d4
Revises: f2c8a4e6b0d1
Create Date: 2026-10-23 09:00:00.000000

Deleting a log used to drop the line and keep everything the act had paid. A
log now carries `undo`, JSON with what its act changed — the action, the mark
event, the profile's marks, the tokens, the hp, and the marks each leaf and
custom attribute received — so deleting it takes all of that back. Logs written
before this column have none; main._legacy_undo rebuilds it from the log's
name, time and marks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c6e8f0b2d4"
down_revision: Union[str, None] = "f2c8a4e6b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("logs", sa.Column("undo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("logs", "undo")
