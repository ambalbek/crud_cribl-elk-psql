"""Drop workspace and worker_group columns, convert environment to JSONB array

Revision ID: 006_drop_workspace_worker_group
Revises: 005_storage_gate
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006_drop_workspace_worker_group"
down_revision = "005_storage_gate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("onboarding_requests", "workspace")
    op.drop_column("onboarding_requests", "worker_group")

    # Convert environment from enum/varchar to JSONB array
    op.execute(
        "ALTER TABLE onboarding_requests "
        "ALTER COLUMN environment TYPE jsonb "
        "USING jsonb_build_array(environment)"
    )


def downgrade() -> None:
    # Convert environment back to varchar (take first element)
    op.execute(
        "ALTER TABLE onboarding_requests "
        "ALTER COLUMN environment TYPE varchar "
        "USING (environment->>0)"
    )
    op.add_column("onboarding_requests", sa.Column("worker_group", sa.String(128), nullable=True))
    op.add_column("onboarding_requests", sa.Column("workspace", sa.String(64), nullable=True))
