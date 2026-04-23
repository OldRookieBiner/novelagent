"""add outline enhancement fields

Revision ID: outline_enhancement
Revises: 20260423_add_review_fields
Create Date: 2026-04-23

添加 Outline 模型的增强字段：
- characters: 人物设定列表
- world_setting: 世界观设定
- emotional_curve: 情感曲线描述
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'outline_enhancement'
down_revision = '20260423_add_review_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 characters 字段（JSON 类型）
    op.add_column(
        'outlines',
        sa.Column('characters', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='[]')
    )

    # 添加 world_setting 字段（JSON 类型）
    op.add_column(
        'outlines',
        sa.Column('world_setting', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='{}')
    )

    # 添加 emotional_curve 字段（String 类型）
    op.add_column(
        'outlines',
        sa.Column('emotional_curve', sa.String(500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('outlines', 'emotional_curve')
    op.drop_column('outlines', 'world_setting')
    op.drop_column('outlines', 'characters')
