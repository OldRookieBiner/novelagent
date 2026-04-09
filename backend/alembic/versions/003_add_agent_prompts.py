"""add agent prompts tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trigger function for auto-updating updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Create agent_prompts table
    op.create_table(
        'agent_prompts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'agent_type', name='uq_user_agent_type')
    )
    op.create_index('ix_agent_prompts_user_id', 'agent_prompts', ['user_id'])

    # Create trigger for agent_prompts
    op.execute("""
        CREATE TRIGGER update_agent_prompts_updated_at
            BEFORE UPDATE ON agent_prompts
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create project_agent_prompts table
    op.create_table(
        'project_agent_prompts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'agent_type', name='uq_project_agent_type')
    )
    op.create_index('ix_project_agent_prompts_project_id', 'project_agent_prompts', ['project_id'])

    # Create trigger for project_agent_prompts
    op.execute("""
        CREATE TRIGGER update_project_agent_prompts_updated_at
            BEFORE UPDATE ON project_agent_prompts
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_project_agent_prompts_updated_at ON project_agent_prompts;")
    op.execute("DROP TRIGGER IF EXISTS update_agent_prompts_updated_at ON agent_prompts;")

    # Drop tables
    op.drop_index('ix_project_agent_prompts_project_id', table_name='project_agent_prompts')
    op.drop_table('project_agent_prompts')
    op.drop_index('ix_agent_prompts_user_id', table_name='agent_prompts')
    op.drop_table('agent_prompts')

    # Drop trigger function (keep if other tables use it, but for clean migration we drop it)
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")