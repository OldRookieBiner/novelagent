"""add style indicator fields (ai_marker_density, sentence_variety)

Revision ID: 20260618_style_indicators
Revises: ef95843c0cfd
Create Date: 2026-06-18

新增 style_snapshots 表的两个指标字段：
- ai_marker_density: AI 味浓度（FORBIDDEN_WORDS 字符出现率）
- sentence_variety: 句长变异性（句长标准差）
"""

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260618_style_indicators"
down_revision: Union[str, None] = "ef95843c0cfd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "style_snapshots",
        sa.Column("ai_marker_density", sa.Float(), server_default="0.0", nullable=True),
    )
    op.add_column(
        "style_snapshots",
        sa.Column("sentence_variety", sa.Float(), server_default="0.0", nullable=True),
    )


def downgrade() -> None:
    op.drop_column("style_snapshots", "sentence_variety")
    op.drop_column("style_snapshots", "ai_marker_density")
