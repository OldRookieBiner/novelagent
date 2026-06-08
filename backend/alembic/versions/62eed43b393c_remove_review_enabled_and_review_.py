# backend/alembic/versions/62eed43b393c_remove_review_enabled_and_review_.py
"""remove review_enabled and review_strictness from user_settings

Revision ID: 62eed43b393c
Revises: 20260608_drop_system_config
Create Date: 2026-06-08 05:21:34.505376

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62eed43b393c'
down_revision: Union[str, None] = '20260608_drop_system_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('user_settings', 'review_enabled')
    op.drop_column('user_settings', 'review_strictness')


def downgrade() -> None:
    op.add_column('user_settings', sa.Column('review_enabled', sa.Boolean(), nullable=True))
    op.add_column('user_settings', sa.Column('review_strictness', sa.String(20), nullable=True))
