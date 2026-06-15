"""add unique project_id to workflow_states

Revision ID: ef95843c0cfd
Revises: a7b1c4b61c59
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef95843c0cfd'
down_revision: Union[str, None] = 'a7b1c4b61c59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 去重：每个 project_id 只保留 id 最大的行（最新记录）
    # 使用原始 SQL 执行，避免 ORM 层面问题
    op.execute("""
        DELETE FROM workflow_states
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM workflow_states
            GROUP BY project_id
        )
    """)

    # 2. 添加 unique 约束
    op.create_unique_constraint(
        'uq_workflow_states_project_id',
        'workflow_states',
        ['project_id']
    )


def downgrade() -> None:
    # 1. 删除 unique 约束
    op.drop_constraint(
        'uq_workflow_states_project_id',
        'workflow_states',
        type_='unique'
    )
