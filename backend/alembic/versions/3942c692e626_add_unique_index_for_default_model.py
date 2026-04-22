# backend/alembic/script.py.mako
"""add_unique_index_for_default_model

Revision ID: 3942c692e626
Revises: 0ce3101355a6
Create Date: 2026-04-22 15:16:37.006106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3942c692e626'
down_revision: Union[str, None] = '0ce3101355a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建部分唯一索引：每个用户只能有一个默认模型
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_model_configs_user_default
        ON model_configs (user_id)
        WHERE is_default = true
    """)


def downgrade() -> None:
    # 删除部分唯一索引
    op.execute("""
        DROP INDEX IF EXISTS idx_model_configs_user_default
    """)