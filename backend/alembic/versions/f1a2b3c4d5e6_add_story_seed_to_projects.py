"""add_story_seed_to_projects

Revision ID: f1a2b3c4d5e6
Revises: e0b17884e4b3
Create Date: 2026-06-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = '20260529_agent_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('story_seed', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'story_seed')
