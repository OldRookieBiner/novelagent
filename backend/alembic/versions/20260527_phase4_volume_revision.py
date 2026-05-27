"""Phase 4: Volume enhancement + cross-volume tracking models

Revision ID: 20260527_phase4_volume_revision
Revises: 20260527_phase2_setting_change
Create Date: 2026-05-27

Changes:
- Add chapter_offset, character_snapshot, last_block_summary to volumes
- Create cross_volume_foreshadowings table
- Create cross_volume_subplots table
- Create character_change_logs table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260527_phase4_volume_revision"
down_revision = "20260527_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns to volumes table
    op.add_column("volumes", sa.Column("chapter_offset", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("volumes", sa.Column("character_snapshot", postgresql.JSON(), nullable=True))
    op.add_column("volumes", sa.Column("last_block_summary", sa.Text(), nullable=True))

    # 2. Create cross_volume_foreshadowings table
    op.create_table(
        "cross_volume_foreshadowings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_foreshadowing_id", sa.Integer(), sa.ForeignKey("foreshadowings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appearance_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expected_volume", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cross_volume_foreshadowings_id", "cross_volume_foreshadowings", ["id"])
    op.create_index("ix_cross_volume_foreshadowings_project", "cross_volume_foreshadowings", ["project_id"])

    # 3. Create cross_volume_subplots table
    op.create_table(
        "cross_volume_subplots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_subplot_id", sa.Integer(), sa.ForeignKey("subplots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("expected_intersection_volume", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cross_volume_subplots_id", "cross_volume_subplots", ["id"])
    op.create_index("ix_cross_volume_subplots_project", "cross_volume_subplots", ["project_id"])

    # 4. Create character_change_logs table
    op.create_table(
        "character_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changes", postgresql.JSON(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_character_change_logs_id", "character_change_logs", ["id"])
    op.create_index("ix_character_change_logs_project", "character_change_logs", ["project_id"])


def downgrade() -> None:
    op.drop_table("character_change_logs")
    op.drop_table("cross_volume_subplots")
    op.drop_table("cross_volume_foreshadowings")
    op.drop_column("volumes", "last_block_summary")
    op.drop_column("volumes", "character_snapshot")
    op.drop_column("volumes", "chapter_offset")
