"""add creation agent models

Revision ID: 20260527_creation
Revises: ae95e3f489f1
Create Date: 2026-05-27

New tables for the creation agent:
- world_settings, style_constraints
- plot_blocks, plot_questions, subplots
- foreshadowings, timeline_entries
- style_snapshots, scene_entries (new columns)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260527_creation'
down_revision = 'ae95e3f489f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # World settings
    op.create_table(
        'world_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('core_concept', sa.Text(), nullable=True),
        sa.Column('tiered_settings', postgresql.JSON(), nullable=True),
        sa.Column('key_locations', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_world_settings_id'), 'world_settings', ['id'])
    op.create_unique_constraint('uq_world_settings_project_id', 'world_settings', ['project_id'])

    # Style constraints
    op.create_table(
        'style_constraints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('taboo_words', postgresql.JSON(), nullable=True),
        sa.Column('forbidden_patterns', postgresql.JSON(), nullable=True),
        sa.Column('style_anchor', sa.Text(), nullable=True),
        sa.Column('abstract_rules', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_style_constraints_id'), 'style_constraints', ['id'])
    op.create_unique_constraint('uq_style_constraints_project_id', 'style_constraints', ['project_id'])

    # Plot blocks
    op.create_table(
        'plot_blocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('questions_to_answer', postgresql.JSON(), nullable=True),
        sa.Column('questions_to_raise', postgresql.JSON(), nullable=True),
        sa.Column('must_happen', postgresql.JSON(), nullable=True),
        sa.Column('expected_mood', sa.String(length=100), nullable=True),
        sa.Column('chapter_start', sa.Integer(), nullable=True),
        sa.Column('chapter_end', sa.Integer(), nullable=True),
        sa.Column('completion_summary', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_plot_blocks_id'), 'plot_blocks', ['id'])

    # Plot questions
    op.create_table(
        'plot_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('plot_block_id', sa.Integer(), nullable=True),
        sa.Column('question_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('raised_in_chapter', sa.Integer(), nullable=True),
        sa.Column('answered_in_chapter', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plot_block_id'], ['plot_blocks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_plot_questions_id'), 'plot_questions', ['id'])

    # Subplots
    op.create_table(
        'subplots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('characters', postgresql.JSON(), nullable=True),
        sa.Column('current_status', sa.String(length=100), nullable=True),
        sa.Column('raised_in_chapter', sa.Integer(), nullable=True),
        sa.Column('planned_intersection_chapter', sa.Integer(), nullable=True),
        sa.Column('expected_resolution_chapter', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subplots_id'), 'subplots', ['id'])

    # Foreshadowings
    op.create_table(
        'foreshadowings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=True),
        sa.Column('appearance_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('planted_chapter', sa.Integer(), nullable=True),
        sa.Column('expected_resolve_chapter', sa.Integer(), nullable=True),
        sa.Column('resolved_chapter', sa.Integer(), nullable=True),
        sa.Column('related_characters', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_foreshadowings_id'), 'foreshadowings', ['id'])

    # Timeline entries
    op.create_table(
        'timeline_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('causal_chain', sa.Text(), nullable=True),
        sa.Column('rhythm_score', sa.Integer(), nullable=True),
        sa.Column('tension_score', sa.Integer(), nullable=True),
        sa.Column('emotion_score', sa.Integer(), nullable=True),
        sa.Column('emotion_tag', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_timeline_entries_id'), 'timeline_entries', ['id'])

    # Style snapshots
    op.create_table(
        'style_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('paragraph_count', sa.Integer(), nullable=True),
        sa.Column('avg_paragraph_length', sa.Float(), nullable=True),
        sa.Column('dialogue_ratio', sa.Float(), nullable=True),
        sa.Column('avg_sentence_length', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_style_snapshots_id'), 'style_snapshots', ['id'])

    # Scene entries (new table)
    op.create_table(
        'scene_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('scene_index', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('scene_description', sa.Text(), nullable=True),
        sa.Column('characters_present', postgresql.JSON(), nullable=True),
        sa.Column('mood', sa.String(length=50), nullable=True),
        sa.Column('key_events', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scene_entries_id'), 'scene_entries', ['id'])


def downgrade() -> None:
    op.drop_table('scene_entries')
    op.drop_table('style_snapshots')
    op.drop_table('timeline_entries')
    op.drop_table('foreshadowings')
    op.drop_table('subplots')
    op.drop_table('plot_questions')
    op.drop_table('plot_blocks')
    op.drop_table('style_constraints')
    op.drop_table('world_settings')
