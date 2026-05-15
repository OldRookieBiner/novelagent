# backend/alembic/script.py.mako
"""add_chapter_outline_fields

Revision ID: e0b17884e4b3
Revises: 50019c738b72
Create Date: 2026-05-15 15:53:32.476932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0b17884e4b3'
down_revision: Union[str, None] = '50019c738b72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 章节大纲新增字段：转折点、悬念钩子、过渡衔接
    op.add_column('chapter_outlines', sa.Column('turning_point', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('hook', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('transition', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('chapter_outlines', 'transition')
    op.drop_column('chapter_outlines', 'hook')
    op.drop_column('chapter_outlines', 'turning_point')