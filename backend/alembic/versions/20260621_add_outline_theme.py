"""add theme to outlines

Revision ID: 20260621_outline_theme
Revises: 20260621_char_knowledge
Create Date: 2026-06-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260621_outline_theme"
down_revision: Union[str, None] = "20260621_char_knowledge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outlines",
        sa.Column("theme", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("outlines", "theme")
