"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # User settings table
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('model_provider', sa.String(50), nullable=True, default='deepseek'),
        sa.Column('model_name', sa.String(100), nullable=True, default='deepseek-chat'),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('review_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('review_strictness', sa.String(20), nullable=True, default='standard'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # Projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('stage', sa.String(50), nullable=True, default='collecting_info'),
        sa.Column('target_words', sa.Integer(), nullable=True, default=100000),
        sa.Column('total_words', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    # Outlines table
    op.create_table(
        'outlines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('plot_points', sa.JSON(), nullable=True),
        sa.Column('collected_info', sa.JSON(), nullable=True),
        sa.Column('chapter_count_suggested', sa.Integer(), nullable=True, default=0),
        sa.Column('chapter_count_confirmed', sa.Boolean(), nullable=True, default=False),
        sa.Column('confirmed', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id')
    )

    # Chapter outlines table
    op.create_table(
        'chapter_outlines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('scene', sa.String(500), nullable=True),
        sa.Column('characters', sa.Text(), nullable=True),
        sa.Column('plot', sa.Text(), nullable=True),
        sa.Column('conflict', sa.Text(), nullable=True),
        sa.Column('ending', sa.Text(), nullable=True),
        sa.Column('target_words', sa.Integer(), nullable=True, default=3000),
        sa.Column('confirmed', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chapter_outlines_project_id', 'chapter_outlines', ['project_id'])

    # Chapters table
    op.create_table(
        'chapters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_outline_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True, default=0),
        sa.Column('review_passed', sa.Boolean(), nullable=True, default=False),
        sa.Column('review_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chapter_outline_id'], ['chapter_outlines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chapter_outline_id')
    )


def downgrade() -> None:
    op.drop_table('chapters')
    op.drop_table('chapter_outlines')
    op.drop_table('outlines')
    op.drop_table('projects')
    op.drop_table('user_settings')
    op.drop_table('users')