"""add workflow fields and checkpoint table

Revision ID: 20260423_workflow
Revises: outline_enhancement
Create Date: 2026-04-23

添加 workflow_mode 字段和 workflow_checkpoints 表：
- projects.workflow_mode: 工作流模式 (hybrid/step/continuous)
- workflow_checkpoints: LangGraph 状态持久化表
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260423_workflow'
down_revision = 'outline_enhancement'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 workflow_mode 字段到 projects 表
    op.add_column(
        'projects',
        sa.Column('workflow_mode', sa.String(20), nullable=False, server_default='hybrid')
    )

    # 创建 workflow_checkpoints 表
    op.create_table(
        'workflow_checkpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(100), nullable=False),
        sa.Column('checkpoint', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('idx_checkpoints_project', 'workflow_checkpoints', ['project_id'])
    op.create_index('idx_checkpoints_thread', 'workflow_checkpoints', ['thread_id'])

    # 创建唯一约束
    op.create_unique_constraint(
        'uq_checkpoints_project_thread',
        'workflow_checkpoints',
        ['project_id', 'thread_id']
    )


def downgrade() -> None:
    # 删除唯一约束
    op.drop_constraint('uq_checkpoints_project_thread', 'workflow_checkpoints')

    # 删除索引
    op.drop_index('idx_checkpoints_thread', table_name='workflow_checkpoints')
    op.drop_index('idx_checkpoints_project', table_name='workflow_checkpoints')

    # 删除表
    op.drop_table('workflow_checkpoints')

    # 删除 workflow_mode 字段
    op.drop_column('projects', 'workflow_mode')
