"""add is_busy fields to projects

Revision ID: 20260523_busy
Revises: 20260518_arc_outline
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa

revision = '20260523_busy'
down_revision = '20260518_arc_outline'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'projects',
        sa.Column('is_busy', sa.Boolean(), server_default='false', nullable=False)
    )
    op.add_column(
        'projects',
        sa.Column('busy_since', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'projects',
        sa.Column('busy_by', sa.String(20), nullable=True)
    )


def downgrade():
    op.drop_column('projects', 'busy_by')
    op.drop_column('projects', 'busy_since')
    op.drop_column('projects', 'is_busy')
