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

    # Storage verification columns
    op.add_column("onboarding_requests", sa.Column("storage_container", sa.String(256), nullable=True))
    op.add_column("onboarding_requests", sa.Column("storage_prefix", sa.String(256), nullable=True))
    op.add_column("onboarding_requests", sa.Column("storage_region", sa.String(64), nullable=True))
    op.add_column("onboarding_requests", sa.Column("storage_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("onboarding_requests", sa.Column("storage_verified_by", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_requests", "storage_verified_by")
    op.drop_column("onboarding_requests", "storage_verified_at")
    op.drop_column("onboarding_requests", "storage_region")
    op.drop_column("onboarding_requests", "storage_prefix")
    op.drop_column("onboarding_requests", "storage_container")
