"""media: titles as tags on the thoughts of acts

Revision ID: e1f3a5b7c9d2
Revises: d0e2f4a6b8c1
Create Date: 2026-10-28 10:00:00.000000

What was watched, read or played lived in the thought's free text ("Jojo 9
41", "Queens caravan") and, by hand, in two lists of ~/journal. A `media` row
is one title of a profile — its kind, its status in the journal's words
(ativo, fila, finalizado, retirado, morto), an optional note such as the
console — and `thoughts.media_id` is the tag: the title a log's thought is
about. Deleting a title leaves its thoughts, untagged.

`patch_action_id` names the patch the title became once it kept coming back
(src.domain.media).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f3a5b7c9d2"
down_revision: Union[str, None] = "d0e2f4a6b8c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="fila"),
        sa.Column("note", sa.String(64), nullable=True),
        sa.Column("patch_action_id", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "kind", "title", name="uq_media_user_kind_title"),
    )
    op.add_column("thoughts", sa.Column("media_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_thoughts_media", "thoughts", "media", ["media_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_thoughts_media", "thoughts", type_="foreignkey")
    op.drop_column("thoughts", "media_id")
    op.drop_table("media")
