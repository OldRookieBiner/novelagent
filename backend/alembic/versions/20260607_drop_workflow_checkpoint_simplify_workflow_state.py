"""drop workflow_checkpoints, simplify workflow_states

Revision ID: 20260607_workflow_cleanup
Revises:
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20260607_workflow_cleanup'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop workflow_checkpoints table
    op.drop_table('workflow_checkpoints')

    # Drop columns from workflow_states
    with op.batch_alter_table('workflow_states') as batch_op:
        batch_op.drop_column('thread_id')
        batch_op.drop_column('workflow_mode')
        batch_op.drop_column('max_rewrite_count')
        batch_op.drop_column('waiting_for_confirmation')
        batch_op.drop_column('confirmation_type')

    # Update default stage from 'inspiration' to 'incubation'
    op.execute(
        "UPDATE workflow_states SET stage = 'incubation' WHERE stage = 'inspiration'"
    )


def downgrade() -> None:
    # Re-add columns to workflow_states
    with op.batch_alter_table('workflow_states') as batch_op:
        batch_op.add_column(sa.Column('thread_id', sa.String(50), nullable=True, server_default='main'))
        batch_op.add_column(sa.Column('workflow_mode', sa.String(20), nullable=True, server_default='hybrid'))
        batch_op.add_column(sa.Column('max_rewrite_count', sa.Integer(), nullable=True, server_default='3'))
        batch_op.add_column(sa.Column('waiting_for_confirmation', sa.Boolean(), nullable=True, server_default='false'))
        batch_op.add_column(sa.Column('confirmation_type', sa.String(30), nullable=True))

    # Recreate workflow_checkpoints table
    op.create_table(
        'workflow_checkpoints',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('thread_id', sa.String(100), nullable=False, index=True),
        sa.Column('checkpoint_id', sa.String(36), nullable=True, index=True),
        sa.Column('checkpoint', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
