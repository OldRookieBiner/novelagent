# backend/alembic/script.py.mako
"""add_llm_config_to_workflow_state

Revision ID: 50019c738b72
Revises: 80f20c045252
Create Date: 2026-05-13 16:39:29.677889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50019c738b72'
down_revision: Union[str, None] = '80f20c045252'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workflow_states', sa.Column('llm_config_id', sa.Integer(), nullable=True))
    op.add_column('workflow_states', sa.Column('llm_model_name', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('workflow_states', 'llm_model_name')
    op.drop_column('workflow_states', 'llm_config_id')