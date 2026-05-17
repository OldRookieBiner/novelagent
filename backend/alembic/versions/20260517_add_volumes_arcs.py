"""add volumes and arcs tables

Revision ID: 20260517_volumes_arcs
Revises: e0b17884e4b3
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260517_volumes_arcs"
down_revision = "e0b17884e4b3"
branch_labels = None
depends_on = None


def upgrade():
    # 创建 volumes 表
    op.create_table(
        "volumes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("volume_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("project_id", "volume_number"),
    )
    op.create_index("ix_volumes_id", "volumes", ["id"])

    # 创建 arcs 表
    op.create_table(
        "arcs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "volume_id",
            sa.Integer(),
            sa.ForeignKey("volumes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("arc_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "chapter_count",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("volume_id", "arc_number"),
    )
    op.create_index("ix_arcs_id", "arcs", ["id"])

    # chapter_outlines 新增 arc_id
    op.add_column(
        "chapter_outlines",
        sa.Column(
            "arc_id",
            sa.Integer(),
            sa.ForeignKey("arcs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # chapters 新增 summary
    op.add_column("chapters", sa.Column("summary", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("chapters", "summary")
    op.drop_column("chapter_outlines", "arc_id")
    op.drop_table("arcs")
    op.drop_table("volumes")
