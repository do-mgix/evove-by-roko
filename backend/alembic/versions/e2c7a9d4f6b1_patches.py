"""patches and user attributes

Revision ID: e2c7a9d4f6b1
Revises: d8e4b2c6f1a3
Create Date: 2026-09-12 12:00:00.000000

Catalog actions become engines a user can specialize. A patch is a row in
`actions` pointing at the action it specializes (`base_action_id`); its id is
the base's id plus two digits. It trains attributes the user creates, which
live outside the default graph in `user_attributes` and follow the same rules
with equal weights: a leaf holds the score, a parent is the mean of its
children.

`patch_attributes` links a patch to its attributes by the patch's action_id
text rather than actions.id, because save_user deletes and reinserts every
action row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2c7a9d4f6b1"
down_revision: Union[str, None] = "d8e4b2c6f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("actions", sa.Column("base_action_id", sa.String(16), nullable=True))

    op.create_table(
        "user_attributes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("user_attributes.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("permanent_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_attributes_name"),
    )

    op.create_table(
        "patch_attributes",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("patch_action_id", sa.String(16), primary_key=True),
        sa.Column("user_attribute_id", sa.BigInteger(), sa.ForeignKey("user_attributes.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("patch_attributes")
    op.drop_table("user_attributes")
    op.execute("DELETE FROM actions WHERE base_action_id IS NOT NULL")
    op.drop_column("actions", "base_action_id")
