"""add agent model selection fields to user_settings

Revision ID: 20260529_agent_model
Revises: 20260527_phase4_volume_revision
Create Date: 2026-05-29

Add agent_model_config_id and agent_model_name to user_settings
for persisting the agent's model selector choice across sessions.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "20260529_agent_model"
down_revision = "20260527_phase4_volume_revision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("agent_model_config_id", sa.Integer(), nullable=True))
    op.add_column("user_settings", sa.Column("agent_model_name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "agent_model_name")
    op.drop_column("user_settings", "agent_model_config_id")
