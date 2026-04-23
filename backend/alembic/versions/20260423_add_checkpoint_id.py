"""add checkpoint_id and fix unique constraint

Revision ID: 20260423_checkpoint_fix
Revises: 20260423_workflow
Create Date: 2026-04-23

修复 workflow_checkpoints 表以支持 LangGraph 的检查点历史：
- 删除 project_id + thread_id 的唯一约束（LangGraph 需要每个线程多个检查点）
- 添加 checkpoint_id 字段（UUID 格式）
- 添加 checkpoint_id 索引
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260423_checkpoint_fix'
down_revision = '20260423_workflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除唯一约束（LangGraph 需要每个线程多个检查点）
    op.drop_constraint('uq_checkpoints_project_thread', 'workflow_checkpoints')

    # 添加 checkpoint_id 字段
    op.add_column(
        'workflow_checkpoints',
        sa.Column('checkpoint_id', sa.String(36), nullable=True)
    )

    # 创建 checkpoint_id 索引
    op.create_index(
        'idx_checkpoints_checkpoint_id',
        'workflow_checkpoints',
        ['checkpoint_id']
    )


def downgrade() -> None:
    # 删除索引
    op.drop_index('idx_checkpoints_checkpoint_id', table_name='workflow_checkpoints')

    # 删除字段
    op.drop_column('workflow_checkpoints', 'checkpoint_id')

    # 恢复唯一约束
    op.create_unique_constraint(
        'uq_checkpoints_project_thread',
        'workflow_checkpoints',
        ['project_id', 'thread_id']
    )
