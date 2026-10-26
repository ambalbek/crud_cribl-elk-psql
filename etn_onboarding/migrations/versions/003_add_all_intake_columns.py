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


def _add_column_if_missing(table, col_name, col_type):
    """Idempotent add_column using PL/pgSQL exception handling."""
    op.execute(f"""
        DO $$ BEGIN
            ALTER TABLE {table} ADD COLUMN {col_name} {col_type};
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)


def upgrade() -> None:
    _add_column_if_missing("onboarding_requests", "lan_id", "VARCHAR(128)")
    _add_column_if_missing("onboarding_requests", "first_name", "VARCHAR(128)")
    _add_column_if_missing("onboarding_requests", "last_name", "VARCHAR(128)")
    _add_column_if_missing("onboarding_requests", "app_emails", "JSONB")
    _add_column_if_missing("onboarding_requests", "workspace", "VARCHAR(64)")
    _add_column_if_missing("onboarding_requests", "worker_group", "VARCHAR(128)")
    _add_column_if_missing("onboarding_requests", "region", "VARCHAR(16)")
    _add_column_if_missing("onboarding_requests", "data_type", "VARCHAR(64)")
    _add_column_if_missing("onboarding_requests", "log_destinations", "JSONB")
    _add_column_if_missing("onboarding_requests", "log_types", "JSONB")
    _add_column_if_missing("onboarding_requests", "ilm_tier", "VARCHAR(32)")
    _add_column_if_missing("onboarding_requests", "entitlement_groups", "JSONB")


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
