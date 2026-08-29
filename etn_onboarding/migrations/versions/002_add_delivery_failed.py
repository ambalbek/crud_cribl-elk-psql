"""Add delivery_failed status to request_status_enum

Revision ID: 002_add_delivery_failed
Revises: 001_initial
Create Date: 2026-08-29
"""
from alembic import op

revision = "002_add_delivery_failed"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE request_status_enum ADD VALUE IF NOT EXISTS 'delivery_failed'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum.
    # A full enum rebuild would be needed; left as a no-op because
    # the value is harmless if unused.
    pass
