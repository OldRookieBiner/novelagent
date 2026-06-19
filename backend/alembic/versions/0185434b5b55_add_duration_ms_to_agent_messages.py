"""add duration_ms to agent_messages

Revision ID: 0185434b5b55
Revises: 20260618_style_indicators
Create Date: 2026-06-19 11:51:21.517508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0185434b5b55'
down_revision: Union[str, None] = '20260618_style_indicators'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'agent_messages',
        sa.Column('duration_ms', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('agent_messages', 'duration_ms')
