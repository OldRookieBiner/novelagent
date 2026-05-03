# backend/alembic/script.py.mako
"""change emotional_curve from String(500) to Text

Revision ID: 899bf73bcc51
Revises: 0aec94f8dce4
Create Date: 2026-05-03 09:03:05.106405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '899bf73bcc51'
down_revision: Union[str, None] = '0aec94f8dce4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'outlines', 'emotional_curve',
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        'outlines', 'emotional_curve',
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True
    )