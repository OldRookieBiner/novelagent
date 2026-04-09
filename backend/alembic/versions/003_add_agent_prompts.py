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


def downgrade() -> None:
    op.drop_index('ix_project_agent_prompts_project_id', table_name='project_agent_prompts')
    op.drop_table('project_agent_prompts')
    op.drop_index('ix_agent_prompts_user_id', table_name='agent_prompts')
    op.drop_table('agent_prompts')