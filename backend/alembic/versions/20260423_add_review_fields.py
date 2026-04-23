"""add review fields

Revision ID: 20260423_review
Revises: 3942c692e626
Create Date: 2026-04-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260423_review'
down_revision: Union[str, None] = '3942c692e626'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Project 表新增字段
    op.add_column('projects', sa.Column('review_mode', sa.String(20), nullable=False, server_default='off'))
    op.add_column('projects', sa.Column('max_rewrite_count', sa.Integer, nullable=False, server_default='3'))

    # Chapter 表新增字段
    op.add_column('chapters', sa.Column('review_result', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('chapters', sa.Column('rewrite_count', sa.Integer, nullable=False, server_default='0'))


def downgrade() -> None:
    # Chapter 表移除字段
    op.drop_column('chapters', 'rewrite_count')
    op.drop_column('chapters', 'review_result')

    # Project 表移除字段
    op.drop_column('projects', 'max_rewrite_count')
    op.drop_column('projects', 'review_mode')
