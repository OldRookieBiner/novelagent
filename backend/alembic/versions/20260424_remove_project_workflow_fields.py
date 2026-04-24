"""remove workflow fields from projects table

Revision ID: 20260424_remove_workflow
Revises: 20260424_workflow_state
Create Date: 2026-04-24

删除 projects 表中的工作流相关字段：
- stage（已迁移到 workflow_states 表）
- review_mode（已废弃，不再使用）
- workflow_mode（已迁移到 workflow_states 表）
- max_rewrite_count（已迁移到 workflow_states 表）

这些字段现在由 workflow_states 表管理，实现工作流状态与项目元数据的分离。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260424_remove_workflow'
down_revision = '20260424_workflow_state'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """删除 projects 表中的工作流字段"""
    # 删除 workflow_mode 字段
    op.drop_column('projects', 'workflow_mode')

    # 删除 max_rewrite_count 字段
    op.drop_column('projects', 'max_rewrite_count')

    # 删除 review_mode 字段
    op.drop_column('projects', 'review_mode')

    # 删除 stage 字段
    op.drop_column('projects', 'stage')


def downgrade() -> None:
    """恢复 projects 表中的工作流字段"""
    # 恢复 stage 字段
    op.add_column(
        'projects',
        sa.Column('stage', sa.String(50), nullable=True, server_default='inspiration_collecting')
    )

    # 恢复 review_mode 字段
    op.add_column(
        'projects',
        sa.Column('review_mode', sa.String(20), nullable=True, server_default='off')
    )

    # 恢复 max_rewrite_count 字段
    op.add_column(
        'projects',
        sa.Column('max_rewrite_count', sa.Integer(), nullable=True, server_default='3')
    )

    # 恢复 workflow_mode 字段
    op.add_column(
        'projects',
        sa.Column('workflow_mode', sa.String(20), nullable=True, server_default='hybrid')
    )

    # 从 workflow_states 恢复数据到 projects（可选，仅恢复 main 线程的数据）
    conn = op.get_bind()

    # Stage 映射：新值 -> 旧值
    STAGE_REVERSE_MAPPING = {
        'inspiration': 'inspiration_collecting',
        'outline': 'outline_generating',
        'chapter_outlines': 'chapter_outlines_generating',
        'writing': 'chapter_writing',
        'review': 'chapter_reviewing',
        'complete': 'completed',
    }

    # 获取所有 workflow_states（仅 main 线程）
    workflow_states = conn.execute(
        sa.text("""
            SELECT project_id, stage, workflow_mode, max_rewrite_count
            FROM workflow_states
            WHERE thread_id = 'main'
        """)
    ).fetchall()

    # 更新 projects 表
    for ws in workflow_states:
        project_id, stage, workflow_mode, max_rewrite_count = ws
        old_stage = STAGE_REVERSE_MAPPING.get(stage, 'inspiration_collecting')

        conn.execute(
            sa.text("""
                UPDATE projects
                SET stage = :stage,
                    workflow_mode = :workflow_mode,
                    max_rewrite_count = :max_rewrite_count,
                    review_mode = 'off'
                WHERE id = :project_id
            """),
            {
                "project_id": project_id,
                "stage": old_stage,
                "workflow_mode": workflow_mode or 'hybrid',
                "max_rewrite_count": max_rewrite_count or 3
            }
        )
