"""add workflow_states table

Revision ID: 20260424_workflow_state
Revises: 20260423_checkpoint_fix
Create Date: 2026-04-24

创建 workflow_states 表：
- 分离工作流状态与项目元数据
- 支持多工作流实例（thread_id）
- 统一 stage 命名
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260424_workflow_state'
down_revision = '20260423_checkpoint_fix'
branch_labels = None
depends_on = None

# Stage 值映射：旧值 -> 新值
STAGE_MAPPING = {
    'inspiration_collecting': 'inspiration',
    'outline_generating': 'outline',
    'outline_confirming': 'outline',
    'chapter_outlines_generating': 'chapter_outlines',
    'chapter_outlines_confirming': 'chapter_outlines',
    'chapter_writing': 'writing',
    'chapter_reviewing': 'review',
    'completed': 'complete',
    'paused': 'writing',  # paused 默认回到 writing
}


def upgrade() -> None:
    """创建 workflow_states 表并迁移数据"""
    # 创建 workflow_states 表
    op.create_table(
        'workflow_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(50), nullable=False, server_default='main'),
        sa.Column('stage', sa.String(30), nullable=False, server_default='inspiration'),
        sa.Column('workflow_mode', sa.String(20), nullable=False, server_default='hybrid'),
        sa.Column('max_rewrite_count', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('current_chapter', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('waiting_for_confirmation', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confirmation_type', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('idx_workflow_states_project', 'workflow_states', ['project_id'])
    op.create_index('idx_workflow_states_thread', 'workflow_states', ['thread_id'])

    # 创建唯一约束：每个项目的每个线程只有一个工作流状态
    op.create_unique_constraint(
        'uq_workflow_states_project_thread',
        'workflow_states',
        ['project_id', 'thread_id']
    )

    # 迁移数据：从 projects 表迁移到 workflow_states 表
    conn = op.get_bind()

    # 获取所有项目的工作流相关字段
    projects = conn.execute(
        sa.text("""
            SELECT id, stage, workflow_mode, max_rewrite_count
            FROM projects
        """)
    ).fetchall()

    # 为每个项目创建 workflow_state 记录
    for project in projects:
        project_id, old_stage, workflow_mode, max_rewrite_count = project

        # 转换 stage 值
        new_stage = STAGE_MAPPING.get(old_stage, 'inspiration')

        # 获取当前章节（从已写章节计算下一个要写的章节号）
        current_chapter_result = conn.execute(
            sa.text("""
                SELECT COUNT(*) + 1
                FROM chapter_outlines co
                JOIN chapters c ON c.chapter_outline_id = co.id
                WHERE co.project_id = :project_id
            """),
            {"project_id": project_id}
        ).fetchone()
        current_chapter = current_chapter_result[0] if current_chapter_result else 1

        # 插入 workflow_state 记录
        conn.execute(
            sa.text("""
                INSERT INTO workflow_states
                (project_id, thread_id, stage, workflow_mode, max_rewrite_count, current_chapter,
                 waiting_for_confirmation, created_at, updated_at)
                VALUES (:project_id, 'main', :stage, :workflow_mode, :max_rewrite_count, :current_chapter,
                        false, NOW(), NOW())
            """),
            {
                "project_id": project_id,
                "stage": new_stage,
                "workflow_mode": workflow_mode or 'hybrid',
                "max_rewrite_count": max_rewrite_count or 3,
                "current_chapter": current_chapter
            }
        )


def downgrade() -> None:
    """回滚：删除 workflow_states 表"""
    # 删除唯一约束
    op.drop_constraint('uq_workflow_states_project_thread', 'workflow_states')

    # 删除索引
    op.drop_index('idx_workflow_states_thread', table_name='workflow_states')
    op.drop_index('idx_workflow_states_project', table_name='workflow_states')

    # 删除表
    op.drop_table('workflow_states')
