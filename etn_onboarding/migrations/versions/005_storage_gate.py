"""Add storage gate columns and new delivery states

Revision ID: 005_storage_gate
Revises: 004_pack_registry
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

revision = "005_storage_gate"
down_revision = "004_pack_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New enum values for the reordered delivery flow
    for val in (
        "storage_pending", "storage_confirmed",
        "delivery_destination", "delivery_pack", "delivery_route",
    ):
        op.execute(f"ALTER TYPE request_status_enum ADD VALUE IF NOT EXISTS '{val}'")

    # Storage verification columns (idempotent)
    for col_name, col_type in [
        ("storage_container", "VARCHAR(256)"),
        ("storage_prefix", "VARCHAR(256)"),
        ("storage_region", "VARCHAR(64)"),
        ("storage_verified_at", "TIMESTAMPTZ"),
        ("storage_verified_by", "VARCHAR(256)"),
    ]:
        op.execute(f"""
            DO $$ BEGIN
                ALTER TABLE onboarding_requests ADD COLUMN {col_name} {col_type};
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$;
        """)


def downgrade() -> None:
    op.drop_column("onboarding_requests", "storage_verified_by")
    op.drop_column("onboarding_requests", "storage_verified_at")
    op.drop_column("onboarding_requests", "storage_region")
    op.drop_column("onboarding_requests", "storage_prefix")
    op.drop_column("onboarding_requests", "storage_container")
