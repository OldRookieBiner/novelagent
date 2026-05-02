"""add character tables

Revision ID: 20260428_character_tables
Revises: 20260426_system_prompts
Create Date: 2026-04-28

创建人物设定相关表：
- characters: 人物设定表
- relations: 人物关系表
- evolution_plans: 关系演变规划表
- evolution_records: 关系演变追溯记录表
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260428_character_tables"
down_revision = "20260426_system_prompts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建人物设定相关表"""

    # 1. 创建 characters 表
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("catchphrase", sa.String(200), nullable=True),
        sa.Column("habit_action", sa.String(200), nullable=True),
        sa.Column("deep_fear", sa.Text(), nullable=True),
        sa.Column("core_motivation", sa.Text(), nullable=True),
        sa.Column("growth_arc", sa.Text(), nullable=True),
        sa.Column("appearance", sa.Text(), nullable=True),
        sa.Column("backstory", sa.Text(), nullable=True),
        sa.Column("signature_item", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 创建 characters 表索引
    op.create_index("idx_characters_project", "characters", ["project_id"])
    op.create_index("idx_characters_name", "characters", ["name"])

    # 2. 创建 relations 表
    op.create_table(
        "relations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("character_a_id", sa.Integer(), nullable=False),
        sa.Column("character_b_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False, server_default="双向"),
        sa.Column("current_status", sa.Text(), nullable=True),
        sa.Column("trust_level", sa.Integer(), nullable=True, server_default="50"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["character_a_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["character_b_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 创建 relations 表索引
    op.create_index("idx_relations_project", "relations", ["project_id"])
    op.create_index(
        "idx_relations_characters", "relations", ["character_a_id", "character_b_id"]
    )

    # 3. 创建 evolution_plans 表
    op.create_table(
        "evolution_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("relation_id", sa.Integer(), nullable=False),
        sa.Column("trigger_chapter", sa.Integer(), nullable=False),
        sa.Column("event_description", sa.Text(), nullable=False),
        sa.Column("status_before", sa.Text(), nullable=True),
        sa.Column("status_after", sa.Text(), nullable=False),
        sa.Column("trust_before", sa.Integer(), nullable=True),
        sa.Column("trust_after", sa.Integer(), nullable=True),
        sa.Column("is_triggered", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["relation_id"], ["relations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 创建 evolution_plans 表索引
    op.create_index("idx_evolution_plans_relation", "evolution_plans", ["relation_id"])
    op.create_index(
        "idx_evolution_plans_chapter", "evolution_plans", ["trigger_chapter"]
    )

    # 4. 创建 evolution_records 表
    op.create_table(
        "evolution_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("relation_id", sa.Integer(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status_change", sa.Text(), nullable=True),
        sa.Column("trust_change", sa.Integer(), nullable=True),
        sa.Column("triggered_plan_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["relation_id"], ["relations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["triggered_plan_id"], ["evolution_plans.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 创建 evolution_records 表索引
    op.create_index(
        "idx_evolution_records_relation", "evolution_records", ["relation_id"]
    )
    op.create_index(
        "idx_evolution_records_chapter", "evolution_records", ["chapter_number"]
    )

    # 5. 添加 novel_length 字段到 projects 表
    op.add_column(
        "projects",
        sa.Column("novel_length", sa.Integer(), nullable=True, server_default="100000"),
    )


def downgrade() -> None:
    """回滚：删除人物设定相关表"""

    # 删除 novel_length 字段
    op.drop_column("projects", "novel_length")

    # 删除 evolution_records 表
    op.drop_index("idx_evolution_records_chapter", table_name="evolution_records")
    op.drop_index("idx_evolution_records_relation", table_name="evolution_records")
    op.drop_table("evolution_records")

    # 删除 evolution_plans 表
    op.drop_index("idx_evolution_plans_chapter", table_name="evolution_plans")
    op.drop_index("idx_evolution_plans_relation", table_name="evolution_plans")
    op.drop_table("evolution_plans")

    # 删除 relations 表
    op.drop_index("idx_relations_characters", table_name="relations")
    op.drop_index("idx_relations_project", table_name="relations")
    op.drop_table("relations")

    # 删除 characters 表
    op.drop_index("idx_characters_name", table_name="characters")
    op.drop_index("idx_characters_project", table_name="characters")
    op.drop_table("characters")
