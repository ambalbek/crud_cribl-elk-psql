"""Add all user-submitted fields as proper columns for auditability

Revision ID: 003_add_all_intake_columns
Revises: 002_add_delivery_failed
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003_add_all_intake_columns"
down_revision = "002_add_delivery_failed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onboarding_requests", sa.Column("lan_id", sa.String(128), nullable=True))
    op.add_column("onboarding_requests", sa.Column("first_name", sa.String(128), nullable=True))
    op.add_column("onboarding_requests", sa.Column("last_name", sa.String(128), nullable=True))
    op.add_column("onboarding_requests", sa.Column("app_emails", JSONB, nullable=True))
    op.add_column("onboarding_requests", sa.Column("workspace", sa.String(64), nullable=True))
    op.add_column("onboarding_requests", sa.Column("worker_group", sa.String(128), nullable=True))
    op.add_column("onboarding_requests", sa.Column("region", sa.String(16), nullable=True))
    op.add_column("onboarding_requests", sa.Column("data_type", sa.String(64), nullable=True))
    op.add_column("onboarding_requests", sa.Column("log_destinations", JSONB, nullable=True))
    op.add_column("onboarding_requests", sa.Column("log_types", JSONB, nullable=True))
    op.add_column("onboarding_requests", sa.Column("ilm_tier", sa.String(32), nullable=True))
    op.add_column("onboarding_requests", sa.Column("entitlement_groups", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_requests", "entitlement_groups")
    op.drop_column("onboarding_requests", "ilm_tier")
    op.drop_column("onboarding_requests", "log_types")
    op.drop_column("onboarding_requests", "log_destinations")
    op.drop_column("onboarding_requests", "data_type")
    op.drop_column("onboarding_requests", "region")
    op.drop_column("onboarding_requests", "worker_group")
    op.drop_column("onboarding_requests", "workspace")
    op.drop_column("onboarding_requests", "app_emails")
    op.drop_column("onboarding_requests", "last_name")
    op.drop_column("onboarding_requests", "first_name")
    op.drop_column("onboarding_requests", "lan_id")
