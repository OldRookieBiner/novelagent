"""add setting_changes table for impact assessment

Revision ID: 20260527_phase2
Revises: 20260527_creation
Create Date: 2026-05-27

Phase 2: Knowledge base change proposal + impact assessment tracking.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260527_phase2'
down_revision = '20260527_creation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'setting_changes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('old_value', postgresql.JSON(), nullable=True),
        sa.Column('new_value', postgresql.JSON(), nullable=False),
        sa.Column('status', sa.String(20), server_default='proposed'),
        sa.Column('impact_report', postgresql.JSON(), nullable=True),
        sa.Column('author_decision', sa.String(20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_setting_changes_id', 'setting_changes', ['id'])
    op.create_index('ix_setting_changes_project_id', 'setting_changes', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_setting_changes_project_id')
    op.drop_index('ix_setting_changes_id')
    op.drop_table('setting_changes')
