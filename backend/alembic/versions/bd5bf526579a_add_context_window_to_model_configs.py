# backend/alembic/script.py.mako
"""add_context_window_to_model_configs

Revision ID: bd5bf526579a
Revises: 20260518_arc_outline
Create Date: 2026-05-21 17:50:53.996006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd5bf526579a'
down_revision: Union[str, None] = '20260518_arc_outline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('model_configs', sa.Column(
        'context_window', sa.Integer(), nullable=True,
        comment='模型上下文窗口大小（token 数）'
    ))


def downgrade() -> None:
    op.drop_column('model_configs', 'context_window')
