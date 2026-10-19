"""Add elk_capacity column to onboarding_requests

Revision ID: 008_add_elk_capacity_column
Revises: 007_add_offboarded_status
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008_add_elk_capacity_column"
down_revision = "007_add_offboarded_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Column may already exist if created by the framework's model
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE onboarding_requests ADD COLUMN elk_capacity JSONB;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    # Backfill from form_data where elk_capacity was previously stored
    op.execute("""
        UPDATE onboarding_requests
        SET elk_capacity = (form_data->>'elk_capacity')::jsonb
        WHERE elk_capacity IS NULL
          AND form_data->>'elk_capacity' IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("onboarding_requests", "elk_capacity")
