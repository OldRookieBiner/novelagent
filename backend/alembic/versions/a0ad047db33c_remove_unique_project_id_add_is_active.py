# backend/alembic/script.py.mako
"""remove_unique_project_id_add_is_active

Revision ID: a0ad047db33c
Revises: 62eed43b393c
Create Date: 2026-06-10 03:09:02.275481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a0ad047db33c'
down_revision: Union[str, None] = '62eed43b393c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加 is_active 列（先允许 NULL 以便回填）
    op.add_column('agent_conversations', sa.Column('is_active', sa.Boolean(), nullable=True))
    
    # 2. 回填现有数据：现有会话设为活跃
    op.execute("UPDATE agent_conversations SET is_active = true")
    
    # 3. 设置 NOT NULL + server default
    op.alter_column('agent_conversations', 'is_active', nullable=False, server_default=sa.text('false'))
    
    # 4. 移除 unique constraint
    op.drop_constraint(op.f('agent_conversations_project_id_key'), 'agent_conversations', type_='unique')


def downgrade() -> None:
    # 1. 移除 is_active 列
    op.alter_column('agent_conversations', 'is_active', nullable=True, server_default=None)
    op.drop_column('agent_conversations', 'is_active')
    
    # 2. 重建 unique constraint
    op.create_unique_constraint(
        op.f('agent_conversations_project_id_key'), 
        'agent_conversations', 
        ['project_id'],
        postgresql_nulls_not_distinct=False
    )
