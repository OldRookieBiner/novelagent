"""Drop system_config table

Revision ID: 20260608_drop_system_config
Revises: 20260607_workflow_cleanup
Create Date: 2026-06-08

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "20260608_drop_system_config"
down_revision = "20260607_workflow_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("system_config")


def downgrade():
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
