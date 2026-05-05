# backend/alembic/script.py.mako
"""add checkpoint project thread index

Revision ID: 80f20c045252
Revises: 899bf73bcc51
Create Date: 2026-05-05 06:45:20.235746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80f20c045252'
down_revision: Union[str, None] = '899bf73bcc51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 workflow_checkpoints 复合索引"""
    op.create_index(
        'idx_checkpoint_project_thread_updated',
        'workflow_checkpoints',
        ['project_id', 'thread_id', 'updated_at'],
        postgresql_using='btree',
    )


def downgrade() -> None:
    """删除 workflow_checkpoints 复合索引"""
    op.drop_index('idx_checkpoint_project_thread_updated')