"""add knowledge_boundary/speech_style/speech_samples to characters

Revision ID: 20260621_char_knowledge
Revises: 0185434b5b55
Create Date: 2026-06-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260621_char_knowledge'
down_revision: Union[str, None] = '0185434b5b55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'characters',
        sa.Column('knowledge_boundary', sa.Text(), nullable=True)
    )
    op.add_column(
        'characters',
        sa.Column('speech_style', sa.Text(), nullable=True)
    )
    op.add_column(
        'characters',
        sa.Column('speech_samples', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('characters', 'speech_samples')
    op.drop_column('characters', 'speech_style')
    op.drop_column('characters', 'knowledge_boundary')
