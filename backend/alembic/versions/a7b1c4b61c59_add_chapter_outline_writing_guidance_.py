# backend/alembic/script.py.mako
"""add_chapter_outline_writing_guidance_fields

Revision ID: a7b1c4b61c59
Revises: a0ad047db33c
Create Date: 2026-06-12 00:25:30.884917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b1c4b61c59'
down_revision: Union[str, None] = 'a0ad047db33c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chapter_outlines', sa.Column('opening_state', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('emotional_arc', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('key_scenes', sa.JSON(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('pacing_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('chapter_outlines', 'pacing_note')
    op.drop_column('chapter_outlines', 'key_scenes')
    op.drop_column('chapter_outlines', 'emotional_arc')
    op.drop_column('chapter_outlines', 'opening_state')
