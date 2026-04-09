"""Add performance indexes

Revision ID: 002
Revises: 001
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for chapter_outlines queries
    op.create_index(
        'ix_chapter_outlines_project_chapter',
        'chapter_outlines',
        ['project_id', 'chapter_number'],
        unique=True
    )

    # Index for chapter outline lookup by project
    op.create_index(
        'ix_chapters_chapter_outline_id',
        'chapters',
        ['chapter_outline_id']
    )

    # Index for outline project lookup
    op.create_index(
        'ix_outlines_project_id',
        'outlines',
        ['project_id']
    )


def downgrade() -> None:
    op.drop_index('ix_outlines_project_id', 'outlines')
    op.drop_index('ix_chapters_chapter_outline_id', 'chapters')
    op.drop_index('ix_chapter_outlines_project_chapter', 'chapter_outlines')