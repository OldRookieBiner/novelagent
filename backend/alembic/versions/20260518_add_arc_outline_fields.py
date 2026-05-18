"""add arc outline fields

Revision ID: 20260518_arc_outline
Revises: 20260517_volumes_arcs
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "20260518_arc_outline"
down_revision = "20260517_volumes_arcs"
branch_labels = None
depends_on = None


def upgrade():
    # arcs 表新增 outline 和 outline_confirmed 字段
    op.add_column("arcs", sa.Column("outline", sa.Text(), nullable=True))
    op.add_column(
        "arcs",
        sa.Column(
            "outline_confirmed",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("arcs", "outline_confirmed")
    op.drop_column("arcs", "outline")
