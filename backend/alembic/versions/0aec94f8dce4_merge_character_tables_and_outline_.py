# backend/alembic/script.py.mako
"""merge character_tables and outline_prompt_v2

Revision ID: 0aec94f8dce4
Revises: 20260428_character_tables, 20260502_outline_prompt_v2
Create Date: 2026-05-03 09:03:00.549456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0aec94f8dce4'
down_revision: Union[str, None] = ('20260428_character_tables', '20260502_outline_prompt_v2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass